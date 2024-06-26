from gevent import monkey
monkey.patch_all()

from threading import Thread
from time import sleep, time
import yt_dlp
from flask import request
from gevent.pywsgi import WSGIServer
from random import choice
from requests import get, post
from json import dumps
from bs4 import BeautifulSoup
from randomisedString import Generator as randomStringGenerator
from customisedLogs import Manager as LogManager

from dynamicWebsite import createApps, BaseViewer
from Enum import storageRoutes, CommonMethods, urlTypes, CustomErrors, Constants, folderLocation, Tables
from CustomSong import Song
from SpotifyAPIManager import RateLimitedSpotify, SpotifyClientCredentials, CacheFileHandler

logger = LogManager()
sqlPool = CommonMethods.connectMySQL()
YTDlpIdle = True
requestsIdle = True
tempPausedIDS = []
randomGenerator = randomStringGenerator()
cookiejarCookies = yt_dlp.cookies.load_cookies(f"{folderLocation}temp_internal/cookies.txt", None, None)
HEADER_FOR_REQUEST = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.4664.110 Safari/537.36'}

spotify_apis_secrets = sqlPool.execute(f"SELECT {Tables.spotifyAPIS.clientID.value}, {Tables.spotifyAPIS.secret.value} "
                                       f"from {Tables.spotifyAPIS.selfName.value}")
spotifyApis = []
for client_id_dict in spotify_apis_secrets:
    client_id, secret = client_id_dict[Tables.spotifyAPIS.clientID.value], client_id_dict[Tables.spotifyAPIS.secret.value]
    sp_api = RateLimitedSpotify(auth_manager=SpotifyClientCredentials(client_id=client_id, client_secret=secret, cache_handler=CacheFileHandler(f"{folderLocation}temp_internal/spotify_api_{client_id}")))
    sp_api.requests_timeout = 10
    sp_api.retries = 1
    spotifyApis.append(sp_api)


def freeID(_id):
    sleep(120)
    logger.skip("FREE-ID", _id)
    if _id in tempPausedIDS:
        tempPausedIDS.remove(_id)


def freezeID(_id):
    if _id in tempPausedIDS:
        return False
    logger.skip("FROZE-ID", _id)
    tempPausedIDS.append(_id)
    Thread(target=freeID, args=(_id,)).start()
    return True


def addNewSongToDB(song:Song):
    logger.skip("ADD-DB", f"Adding {song.name}")
    #input("CHANGES ABOUT TO BE MADE...")
    song.name = CommonMethods.cleanedTrackName(song.name)
    if song.allyName:
        song.allyName = CommonMethods.cleanedTrackName(song.allyName)
        if not sqlPool.execute(f"SELECT _id from {Tables.otherNames.selfName.value} "
                               f"where {Tables.otherNames.songName.value}=\"{CommonMethods.cleanedTrackName(song.allyName.lower())}\" "
                               f"LIMIT 1"):
            sqlPool.execute(f"INSERT INTO {Tables.otherNames.selfName.value} values("
                            f"\"{song.ID}\", "
                            f"\"{CommonMethods.cleanedTrackName(song.allyName.lower())}\")")
    sqlPool.execute(f"INSERT INTO {Tables.songData.selfName.value} "
                    f"values ("
                    f"\"{song.ID}\", "
                    f"{song.duration}, "
                    f"\"{song.thumbnail}\", "
                    f"\"{song.audioURL}\", "
                    f"now())")
    sqlPool.execute(f"INSERT INTO {Tables.searchData.selfName.value} values ("
                    f"\"{song.ID}\", "
                    f"\"{CommonMethods.cleanedTrackName(song.name)}\", "
                    f"\"{song.spotify}\", "
                    f"\"{song.yt}\")")
    logger.success("ADD-DB", f"Added {song.name}")


def fetchYTDLP(stringValue:str):
    global YTDlpIdle
    logger.skip("YTDLP", f"Waiting {stringValue}")
    waitingSince = time()
    while not YTDlpIdle and time()-waitingSince<10:
        sleep(0.1)
    YTDlpIdle = False
    logger.info("YTDLP", f"Started {stringValue}")
    try:
        with yt_dlp.YoutubeDL({'title': True, 'default_search': 'auto', 'format': 'bestaudio', "quiet": 1, "retries": "infinite", "extractor_retries": 100, "file_access_retries": "infinite", "fragment_retries": "infinite", "socket_timeout":30}) as downloader:
            downloader.cookiejar = cookiejarCookies
            r: dict = downloader.extract_info(stringValue, download=False)
            logger.success("YTDLP", f"Found P1 {stringValue}")
    except:
        try:
            with yt_dlp.YoutubeDL({'title': True, 'default_search': 'auto', "quiet": 1, "retries": "infinite", "extractor_retries": 100, "file_access_retries": "infinite", "fragment_retries": "infinite", "socket_timeout":30}) as downloader:
                downloader.cookiejar = cookiejarCookies
                r: dict = downloader.extract_info(stringValue, download=False)
                logger.success("YTDLP", f"Found P2 {stringValue}")
        except Exception as e:
            logger.failed("YTDLP", f"{stringValue} {repr(e)}")
            raise CustomErrors.noResultYTDLP()
    YTDlpIdle = True
    return r


def playlistExtractor(stringType:str, string):
    logger.skip("PL-EXTRACT", f"Fetching {string} of type {stringType}")
    return_dict = {}
    if stringType == urlTypes.youtube_playlist.value:
        with yt_dlp.YoutubeDL({'format': 'bestaudio/best', 'extract_flat': True}) as downloader:
            downloader.cookiejar = cookiejarCookies
            r = downloader.extract_info(f"https://www.youtube.com/{string}", download=False)
            for entry in r['entries']:
                link = entry['url']
                #name = entry['title']
                return_dict[link] = ""

    elif stringType == urlTypes.spotify_playlist.value:
        try:  # http://127.0.0.1:50000/extract_playlist?type=spotify_playlist&id=playlist/37i9dQZF1DZ06evO22XGKK
            results = choice(spotifyApis).playlist_items(string.split("/")[1])
            while True:
                for _ in results["items"]:
                    #name = _["track"]["name"]
                    #for artistData in _['track']["artists"]:
                    #    if artistData["name"].lower() not in name.lower():
                    #        name += f" {artistData['name']}"
                    link = _["track"]["external_urls"]["spotify"]
                    return_dict[link] = ""
                if results['next']:
                    results = choice(spotifyApis).next(results)
                else:
                    break
        except:
            pass

    elif stringType == urlTypes.spotify_album.value:
        try:  # http://127.0.0.1:50000/extract_playlist?type=spotify_album&id=album/0rcbtltuPNcfIfgmgTIpUf
            results = choice(spotifyApis).album_tracks(string.split("/")[1])
            while True:
                for _ in results['items']:
                    #name = _['name']
                    #for artistData in _["artists"]:
                    #    if artistData["name"].lower() not in name.lower():
                    #        name += f" {artistData['name']}"
                    link = _["external_urls"]['spotify']
                    return_dict[link] = ""
                if results['next']:
                    results = choice(spotifyApis).next(results)
                else:
                    break
        except:
            pass

    elif stringType == urlTypes.spotify_artist.value:
        try:  # http://127.0.0.1:50000/extract_playlist?type=spotify_artist&id=artist/3P4vW5tzQvmuoNaFQqzy9q
            results = choice(spotifyApis).artist_top_tracks(string.split("/")[1])
            while True:
                for _ in results['tracks']:
                    #name = _['name']
                    #for artistData in _["artists"]:
                    #    artistName = artistData['name']
                    #    if artistName.lower() not in name.lower():
                    #        name += f" {artistName}"
                    link = _["external_urls"]['spotify']
                    return_dict[link] = ""
                if results['next']:
                    results = choice(spotifyApis).next(results)
                else:
                    break
        except:
            pass

    listID = []
    for item in list(return_dict.keys()):
        urlType, link = CommonMethods.urlStripper(item)
        songID = fetchSongID(link, 0)["songID"]
        listID.append(songID)
    logger.success("PL-EXTRACT", f"Fetched {string} : {len(listID)}")
    return dumps(listID)


def fetchNewSong(chosenID:str, stringType:str, stringValue:str):
    global requestsIdle
    logger.skip("NEW-SONG", f"Fetching {stringValue} of type {stringType}")
    createdSong:Song = Song()
    if stringType == urlTypes.youtube_url.value:
        for trial in range(5):
            try:
                r = fetchYTDLP("https://"+stringValue)
                break
            except CustomErrors.noResultYTDLP:
                logger.failed("NEW-SONG", "No result from YTDLP")
        else:
            return
        createdSong.yt = stringValue
        createdSong.name = r.get("title")
        createdSong.audioURL = r.get("url")
        createdSong.duration = r.get("duration")
        createdSong.thumbnail = None if not r.get("thumbnails") else r.get("thumbnails")[0]['url']
        try:
            sp_api = choice(spotifyApis)
            _, createdSong.spotify = CommonMethods.urlStripper(sp_api.search(CommonMethods.cleanedTrackName(createdSong.name))['tracks']['items'][0]['external_urls']['spotify'])
        except:
            createdSong.spotify = ""


    elif stringType == urlTypes.spotify_url.value:
        trial = 0
        for _ in range(10):
            try:
                waitingSince = time()
                while not requestsIdle and time()-waitingSince<10:
                    sleep(0.1)
                requestsIdle = False
                req = get("https://"+stringValue+"?nd=1", headers=HEADER_FOR_REQUEST, allow_redirects=True, timeout=10)
                requestsIdle = True
                if req.status_code == 200:
                    trial+=1
                elif req.status_code == 429:
                    print("SPOTIFY REQUEST RATE LIMITED")
                    sleep(120)
                    continue
                web_data = req.text
                req.close()
                track_name = BeautifulSoup(web_data, 'html.parser').find('title')
                if track_name is not None and '| Spotify' in track_name.string:
                    break
                else:
                    if trial > 5:
                        open("fetch_error", "a").write(f"\n[NONAME] {stringValue}")
                        return
                    print(f"[{trial}] NO NAME FOUND SPOTIFY, RETRYING {stringValue}")
            except Exception as e:
                print("RETRYING", repr(e))
        else:
            return
        track, artist = track_name.string.strip().replace("| Spotify", "").split(" - song by ")[0].strip().split(" - song and lyrics by ")
        if artist.lower() not in track.lower():
            track_name = " by ".join((track, artist,))
        else:
            track_name = track
        createdSong.name = track_name
        while track_name:
            r = fetchYTDLP(CommonMethods.cleanedTrackName(track_name) + " lyrics")
            createdSong.spotify = stringValue
            try:
                createdSong.yt = f"www.youtube.com/watch?v={r['entries'][0]['id']}"
                createdSong.audioURL = r['entries'][0]['url']
                createdSong.duration = r['entries'][0]['duration']
                createdSong.thumbnail = r['entries'][0]['thumbnail'] if r['entries'][0]['thumbnail'] else None
                break
            except:
                track_name = " ".join(CommonMethods.cleanedTrackName(track_name).split()[0:-1])
        else:
            open("fetch_error", "a").write(f"\n[YTDLPFAIL] {stringValue}")
            return


    elif stringType == urlTypes.name.value or stringType == urlTypes.unknown.value:
        r = fetchYTDLP(stringValue + " lyrics")
        createdSong.yt = f"www.youtube.com/watch?v={r['entries'][0]['id']}"
        createdSong.allyName = stringValue
        createdSong.name = r.get("title")
        createdSong.audioURL = r['entries'][0]['url']
        createdSong.duration = r['entries'][0]['duration']
        createdSong.thumbnail = r['entries'][0]['thumbnail'] if r['entries'][0]['thumbnail'] else None
        print(f"CAME HERE {createdSong.name}")
        try:
            sp_api = choice(spotifyApis)
            _, createdSong.spotify = CommonMethods.urlStripper(sp_api.search(CommonMethods.cleanedTrackName(createdSong.name))['tracks']['items'][0]['external_urls']['spotify'])
        except:
            createdSong.spotify = ""


    createdSong.ID = chosenID
    songID = checkRepeated(createdSong)
    if songID is None:
        print("[NEW]", createdSong.jsonify())
        addNewSongToDB(createdSong)
    else:
        print("[REPEAT]", songID, createdSong.name)
        sqlPool.execute(f"INSERT INTO {Tables.repeatID.selfName.value} values ("
                        f"\"{chosenID}\", "
                        f"\"{songID}\","
                        f" now())")
    #print(createdSong.spotify)
    sqlPool.execute(f"UPDATE {Tables.newSpotifyURLS.selfName.value} "
                    f"set fetched=1 "
                    f"where url=\"https://{createdSong.spotify}\"")


def checkRepeated(song:Song):
    logger.skip("REPEAT-CHECK", f"Checking {song.name}")
    realID = None
    availableValues = []

    r = sqlPool.execute(f"SELECT {Tables.otherNames.songID.value}, {Tables.otherNames.songName.value} "
                        f"from {Tables.otherNames.selfName.value} where "
                        f"{Tables.otherNames.songName.value}=\"{CommonMethods.cleanedTrackName(song.name.lower())}\" or "
                        f"{Tables.otherNames.songName.value}=\"{song.yt}\" or "
                        f"{Tables.otherNames.songName.value}=\"{song.spotify}\" "
                        f"limit 3")
    for tup in r:
        realID, value = tup[Tables.otherNames.songID.value], tup[Tables.otherNames.songName.value]
        availableValues.append(value if type(value)==str else value.decode())


    r = sqlPool.execute(f"SELECT {Tables.searchData.songID.value}, {Tables.searchData.realName.value}, {Tables.searchData.youtube.value}, {Tables.searchData.spotify.value} "
                        f"from {Tables.searchData.selfName.value} where "
                        f"{Tables.searchData.realName.value}=\"{CommonMethods.cleanedTrackName(song.name)}\" or "
                        f"{Tables.searchData.youtube.value}=\"{song.yt}\" or "
                        f"{Tables.searchData.spotify.value}=\"{song.spotify}\" "
                        f"limit 3")
    for tup in r:
        _id, real_name, yt, spotify = tup[Tables.searchData.songID.value], tup[Tables.searchData.realName.value], tup[Tables.searchData.youtube.value], tup[Tables.searchData.spotify.value]
        real_name = real_name if type(real_name)==str else real_name.decode()
        yt = yt if type(yt)==str else yt.decode()
        spotify = spotify if type(spotify)==str else spotify.decode()

        if real_name==CommonMethods.cleanedTrackName(song.name):
            realID = _id
            availableValues.append(real_name)
        if yt==song.yt:
            realID = _id
            availableValues.append(yt)
        if spotify==song.spotify:
            realID = _id
            availableValues.append(spotify)

    if realID:
        for para in [CommonMethods.cleanedTrackName(song.allyName), CommonMethods.cleanedTrackName(song.name.lower()), song.yt, song.spotify]:
            para = para.strip()
            if para and para not in availableValues:
                sqlPool.execute(f"INSERT INTO {Tables.otherNames.selfName.value} "
                                f"values (\"{realID}\", \"{para}\")",
                                catchErrors=True)
        sqlPool.execute(f"UPDATE {Tables.songData.selfName.value} "
                        f"set {Tables.songData.audioURL.value}=\"{song.audioURL}\", {Tables.songData.audioURLCreatedAt.value}=now() where "
                        f"{Tables.songData.songID.value}=\"{realID}\"")
    return realID


def fetchSongID(stringValue:str, priority:int|None, threaded=True):
    logger.skip("FETCH-ID", f"Fetching ID for {stringValue}")
    stringType = CommonMethods.songStringIdentifier(stringValue)
    songID = None
    otherNamesDictList = sqlPool.execute(f"SELECT {Tables.otherNames.songID.value} from {Tables.otherNames.selfName.value} where "
                                        f"{Tables.otherNames.songName.value}=\"{CommonMethods.cleanedTrackName(stringValue).lower() if stringType == urlTypes.name.value else stringValue}\" "
                                        f"limit 1")
    if otherNamesDictList and otherNamesDictList[0]:
        songID = otherNamesDictList[0][Tables.otherNames.songID.value]
    elif stringType == urlTypes.name.value:
        realNamesDictList = sqlPool.execute(f"SELECT {Tables.searchData.songID.value} from {Tables.searchData.selfName.value} where "
                                           f"{Tables.searchData.realName.value}=\"{CommonMethods.cleanedTrackName(stringValue)}\" "
                                           f"limit 1")
        if realNamesDictList and realNamesDictList[0]:
            songID = realNamesDictList[0][Tables.searchData.songID.value]
    elif stringType == urlTypes.youtube_url.value:
        YTURLDictList = sqlPool.execute(f"SELECT {Tables.searchData.songID.value} from {Tables.searchData.selfName.value} where "
                                       f"{Tables.searchData.youtube.value}=\"{stringValue}\" "
                                       f"limit 1")
        if YTURLDictList and YTURLDictList[0]:
            songID = YTURLDictList[0][Tables.searchData.songID.value]
    elif stringType == urlTypes.spotify_url.value:
        spotifyURLDictList = sqlPool.execute(f"SELECT {Tables.searchData.songID.value} from {Tables.searchData.selfName.value} where "
                                            f"{Tables.searchData.spotify.value}=\"{stringValue}\" "
                                            f"limit 1")
        if spotifyURLDictList and spotifyURLDictList[0]:
            songID = spotifyURLDictList[0][Tables.searchData.songID.value]
    logger.skip("FETCH-ID", f"Old ID {songID} for {stringValue}")
    if songID is None:
        while True:
            songID = randomGenerator.AlphaNumeric(1, 50)
            if (songID and not sqlPool.execute(f"SELECT {Tables.songData.songID.value} from {Tables.songData.selfName.value} where "
                                              f"{Tables.songData.songID.value}=\"{songID}\" limit 1")
                    and not sqlPool.execute(f"SELECT {Tables.repeatID.realID.value} from {Tables.repeatID.selfName.value} where "
                                            f"{Tables.repeatID.realID.value}=\"{songID}\" limit 1")
                    and freezeID(songID)):
                logger.skip("FETCH-ID", f"New ID generated for {stringValue}")
                break
        if threaded:
            Thread(target=fetchNewSong, args=(songID, stringType, stringValue,)).start()
        else:
            fetchNewSong(songID, stringType, stringValue)
    return {"songID":songID}


def fetchSongData(ID:str, priority:str):
    logger.skip("RETRIEVE", f"Retrieving {ID}")
    song:Song = Song()
    while not sqlPool.execute(f"SELECT {Tables.searchData.songID.value} "
                              f"from {Tables.searchData.selfName.value} where "
                              f"{Tables.searchData.songID.value}=\"{ID}\" limit 1"):
        repeatIDDictList = sqlPool.execute(f"SELECT {Tables.repeatID.realID.value} "
                                          f"from {Tables.repeatID.selfName.value} where "
                                          f"{Tables.repeatID.newID.value}=\"{ID}\" limit 1")
        if repeatIDDictList and repeatIDDictList[0]:
            sqlPool.execute(f"DELETE from {Tables.repeatID.selfName.value} where {Tables.repeatID.newID.value}=\"{ID}\"")
            ID = repeatIDDictList[0][Tables.repeatID.realID.value]
        logger.failed("FETCH", f"{ID} not in search_data")
        sleep(0.1)
    while not sqlPool.execute(f"SELECT {Tables.songData.songID.value} from {Tables.songData.selfName.value} where {Tables.songData.songID.value}=\"{ID}\" limit 1"):
        logger.failed("FETCH", f"{ID} not in song_data")
        sleep(0.1)
    finalDict = sqlPool.execute(f"SELECT * from {Tables.searchData.selfName.value} where _id=\"{ID}\" limit 1")[0]
    song.ID, song.name, song.spotify, song.yt = finalDict[Tables.searchData.songID.value], finalDict[Tables.searchData.realName.value],  finalDict[Tables.searchData.spotify.value],  finalDict[Tables.searchData.youtube.value],
    song.spotify = song.spotify.decode()
    song.yt = song.yt.decode()
    if not sqlPool.execute(f"SELECT {Tables.songData.songID.value} from {Tables.songData.selfName.value} where {Tables.songData.songID.value}=\"{ID}\" and timestampdiff(HOUR, {Tables.songData.audioURLCreatedAt.value}, now())<5 limit 1"):
        r = fetchYTDLP("https://"+song.yt)
        sqlPool.execute(f"UPDATE {Tables.songData.selfName.value} set {Tables.songData.audioURL.value}=\"{r['url']}\" where {Tables.songData.songID.value}=\"{ID}\"")
        sqlPool.execute(f"UPDATE {Tables.songData.selfName.value} set {Tables.songData.audioURLCreatedAt.value}=now() where {Tables.songData.songID.value}=\"{ID}\"")
    finalDict = sqlPool.execute(f"SELECT * from song_data where {Tables.songData.songID.value}=\"{ID}\" limit 1")[0]
    song.duration, song.thumbnail, song.audioURL, song.expiry = finalDict[Tables.songData.duration.value], finalDict[Tables.songData.thumbnail.value],  finalDict[Tables.songData.audioURL.value],  finalDict[Tables.songData.audioURLCreatedAt.value]
    song.thumbnail = song.thumbnail.decode()
    song.audioURL = song.audioURL.decode()
    return song.jsonify()







extraHeads = """<style>
  body {
    font-family: Arial, sans-serif;
    margin: 0;
    padding: 0;
    background-color: #f2f2f2;
  }

  .container {
    max-width: 600px;
    margin: 50px auto;
    padding: 20px;
    background-color: #fff;
    border-radius: 8px;
    box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
  }

  h2 {
    text-align: center;
    margin-bottom: 20px;
    color: #333;
  }

  label {
    font-weight: bold;
  }

  input[type="text"] {
    width: 100%;
    padding: 10px;
    margin-bottom: 20px;
    border: 1px solid #ccc;
    border-radius: 4px;
    box-sizing: border-box;
  }

  button[type="submit"] {
    background-color: #4CAF50;
    color: white;
    padding: 10px 20px;
    border: none;
    border-radius: 4px;
    cursor: pointer;
  }

  button[type="submit"]:hover {
    background-color: #45a049;
  }

  audio {
    width: 100%;
    margin-top: 20px;
  }
</style>"""

fernetKey = 'GNwHvssnLQVKYPZk0D_Amy9m3EeSvi6Y1FiHfTO8F48='
appName = "Song Storage"
purposes = ["search"]


def process_form(viewerObj: BaseViewer, form: dict):
    if form is not None:
        purpose = form.pop("PURPOSE")
        if purpose == "search":
            sendForm(viewerObj)
            songName = form["songName"]
            try:
                sendStatus(viewerObj, f"Fetching Song ID for {songName}")
                response = post(f"http://127.0.0.1:{Constants.storagePort.value}{storageRoutes.requestID.value}", data={"string": songName, "priority": 1}, timeout=20, auth=("bhaskar", "Bhariya@1410",))
                r: dict = response.json()
                songID = r["songID"]
                sendStatus(viewerObj, f"ID Fetched: {songID}")
            except Exception as e:
                print(repr(e))
                sendStatus(viewerObj, "Could not fetch ID...")
                return
            try:
                sendStatus(viewerObj, f"Fetching data...")
                response = post(f"http://127.0.0.1:{Constants.storagePort.value}{storageRoutes.requestData.value}", data={"id": songID}, timeout=20, auth=("bhaskar","Bhariya@1410",))
                r = response.json()
                print(dumps(r, indent=4))
                sendDebug(viewerObj, dumps(r, indent=4))
                sendStatus(viewerObj, f"Song ready...")
            except Exception as e:
                print(repr(e))
                sendStatus(viewerObj, "Unable to connect to server...")
                return
            sendAudioPlayer(viewerObj, r.get("audioURL"))

    else:
        print("Disconnected: ", viewerObj.viewerID)


def sendAudioPlayer(viewerObj: BaseViewer, url):
    data = f"""
    <audio id="audioPlayer" src="{url}" controls>
        Your browser does not support the audio element.
    </audio>"""
    viewerObj.queueTurboAction(data, "audioplayer", viewerObj.turboApp.methods.update)


def sendForm(viewerObj: BaseViewer):
    data = f"""
    <form id="songForm" onsubmit="return submit_ws(this)" autocomplete="off">
        {viewerObj.addCSRF("search")}
        <label for="songName">Song Name:</label><br>
        <input type="text" id="songName" name="songName"><br><br>
        <button type="submit">Play Song</button>
    </form>"""
    viewerObj.queueTurboAction(data, "searchform", viewerObj.turboApp.methods.update)


def sendStatus(viewerObj: BaseViewer, string):
    viewerObj.queueTurboAction(string, "status", viewerObj.turboApp.methods.newDiv, removeAfter=3)


def sendDebug(viewerObj: BaseViewer, string):
    string = f"<pre>{string}</pre>"
    viewerObj.queueTurboAction(string, "debug", viewerObj.turboApp.methods.update)


def newVisitor(viewerObj: BaseViewer):
    initial = f"""
    <h2>Song Names Only!</h2>
    <div id="searchform" class="container"></div>
    <div id="audioplayer" class="container"></div>    
    <div id="debug" class="container"></div>
    <div id="status_create"></div>
"""
    viewerObj.queueTurboAction(initial, "mainDiv", viewerObj.turboApp.methods.update)
    sendForm(viewerObj)


baseApp, turboApp = createApps(process_form, newVisitor, appName, storageRoutes.home.value, storageRoutes.WSRoute.value, fernetKey, extraHeads, "Player", False)


@baseApp.route(f"{storageRoutes.requestID.value}", methods=['POST', "GET"])
def _get_song_id():
    if request.method == "POST":
        received = request.form.to_dict()
    else:
        received = request.args.to_dict()
    logger.info("ID-REQ", f"{received.get('type')} {received.get('string')}")
    return fetchSongID(received.get("string"), received.get("priority"))


@baseApp.route(f"{storageRoutes.requestData.value}", methods=['POST', "GET"])
def _get_song_data():
    if request.method == "POST":
        received = request.form.to_dict()
    else:
        received = request.args.to_dict()

    return fetchSongData(received.get("id"), received.get("priority"))


@baseApp.route(f"{storageRoutes.extractPlayList.value}", methods=['POST', "GET"])
def _extract_playlist():
    if request.method == "POST":
        received = request.form.to_dict()
    else:
        received = request.args.to_dict()

    return playlistExtractor(received.get("type"), received.get("id"))

logger.success("SERVER", f"Listening on *:{Constants.storagePort.value}")
WSGIServer(('0.0.0.0', Constants.storagePort.value,), baseApp, log=None).serve_forever()
