from enum import Enum
from pathlib import Path
from re import search, compile
from pooledMySQL import Manager
from discord.ext.commands import Context, check

try: from SecretEnum import MySQLCreds ## change
except: from internal.SecretEnum import MySQLCreds ## change

possibleFolderLocation = ["C:\\24x7\\discord-music-v4\\", "C:\\FILES\\AllProjects\\Python\\DiscordMusic_v4\\", "D:\\testing\\discord-music-v4\\"]
for location in possibleFolderLocation:
    if Path(location).is_dir():
        folderLocation = location
        break
else:
    input("Project directory not found in Enum...")


class Constants(Enum):
    storagePort = 60300
    maxLogsCount = 10000
    defaultBotNickName = "Where NickName?"
    maxTrackNameSaveLength = 200
    maxTrackNameDisplayLength = 100
    disAllowedWords = ["official", "(official lyric video)", "(Lyric Video)", "video", "lyrics", "lyric", "audio", ",", "(", ")"]


class RequiredFiles(Enum):
    botRunnable = Path(folderLocation, r"internal\_run_botHost.py")
    storageRunnable = Path(folderLocation, r"internal\_run_songStorage.py")

    botRequired = [
    "internal/_run_botHost.py",
    "internal/Enum.py",
    "internal/GuildManager.py",
    "internal/CustomSong.py",
    "internal/ModifiedBot.py",
    "internal/SecretEnum.py",
    "internal/SongManager.py",
    "internal/Updater.py",
    ]

    storageRequired = [
    "internal/_run_songStorage.py",
    "internal/Enum.py",
    "internal/CustomSong.py",
    "internal/SpotifyAPIManager.py",
    "internal/Updater.py",
    ]


class Decorators:
    @staticmethod
    def isBotOwner():
        def predicate(ctx: Context):
            return ctx.message.author.id == ctx.bot.application_id
        return check(predicate)


    @staticmethod
    def isGuildOwner():
        def predicate(ctx: Context):
            return ctx.message.author.id == ctx.guild.owner_id or ctx.message.author.id == ctx.bot.application_id
        return check(predicate)


class storageRoutes(Enum):
    home = "/song"
    requestID = "/song_request_id"
    requestData = "/song_request_data"
    extractPlayList = "/song_extract_playlist"
    WSRoute = f"{home}_ws"


class urlTypes(Enum):
    name = "name"
    youtube_url = "yt_url"
    spotify_url = "spotify_url"
    youtube_playlist = "yt_playlist"
    spotify_playlist = "spotify_playlist"
    spotify_album = "spotify_album"
    spotify_artist = "spotify_artist"
    unknown = "unknown"


class errorCodes(Enum):
    invalidSongString = "Input song is not valid."
    userNotInVC = "You are not in a VoiceChannel, please join one before using this command."
    botNotLoggedIn = "Bot isn't logged in, please use /login to register a text channel."
    botPlayingInDifferentChannel = "Bot is playing in a different VoiceChannel"


class CommonMethods:
    @staticmethod
    def connectMySQL():
        for host in MySQLCreds.host.value:
            try:
                mysqlPool = Manager(user=MySQLCreds.userName.value, password=MySQLCreds.password.value, dbName=MySQLCreds.dbName.value, host=host, logFile="mysqllogs")
                mysqlPool.execute("show tables", catchErrors=False, logIntoFile=False)
                return mysqlPool
            except:
                pass

    @staticmethod
    def isValidURL(string: str) -> bool:
        correct = True
        regex = compile("https?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*(),]|%[0-9a-fA-F][0-9a-fA-F])+")
        if not search(regex, string):
            correct = False
        else:
            for sub in ["//", "playlist", "album", "artist"]:
                if string.count(sub) > 1:
                    correct = False
                    break
        return correct


    @staticmethod
    def urlStripper(string: str) -> tuple[urlTypes, str]:
        if "spotify.com" in string:
            if "/track" in string:
                return urlTypes.spotify_url, string.split("?")[0].replace("http://", "").replace("https://", "")
            else:
                urlSplit = string.split('/')
                while len(urlSplit) > 0 and urlSplit[0] not in ["playlist", "artist", "album"]:
                    urlSplit.pop(0)
                urlSplit[-1] = urlSplit[-1].split('?')[0].strip()
                if urlSplit[0] == "playlist":
                    urlType = urlTypes.spotify_playlist
                elif urlSplit[0] == "artist":
                    urlType = urlTypes.spotify_artist
                elif urlSplit[0] == "album":
                    urlType = urlTypes.spotify_album
                else:
                    urlType = urlTypes.unknown
                urlIdentifier = "/".join(urlSplit)

        elif "www.youtu" in string or "youtu.be" in string or "www.music.youtu" in string or "music.youtu" in string:
            string = string.split("?si=")[0]
            if "playlist?list=" in string:
                urlType = urlTypes.youtube_playlist
                urlSplit = string.split('/')
                while len(urlSplit) > 0 and not urlSplit[0].startswith("playlist"):
                    urlSplit.pop(0)
                urlIdentifier = "/".join(urlSplit)
            else:
                urlType = urlTypes.youtube_url
                if "youtu.be/" in string:
                    string = string.replace("www.youtu.be/", "www.youtube.com/watch?v=").replace("youtu.be/", "www.youtube.com/watch?v=")
                urlIdentifier = string.replace("http://", "").replace("https://", "").split("&")[0]
        else:
            urlType = urlTypes.unknown
            urlIdentifier = string
        return urlType, urlIdentifier


    @staticmethod
    def cleanedTrackName(track_name, cleanSymbols:bool=True, size=Constants.maxTrackNameSaveLength.value) -> str:
        track_name = track_name.replace('"', "'")
        if cleanSymbols:
            if not track_name.replace(" ", "").isalnum():
                for index in range(len(track_name)):
                    if not track_name[index].isalnum() and track_name[index] != "'":
                        track_name = track_name.replace(track_name[index], " ")
        word_list = track_name.split()
        track_name = ""
        for word in word_list:
            if len(track_name)+len(word) <= size and word.lower() not in Constants.disAllowedWords.value:
                track_name += word + ' '
        return track_name.strip()


    @staticmethod
    def songStringIdentifier(songString:str) -> tuple[bool, urlTypes, str]:
        isCorrect = False
        if CommonMethods.isValidURL(songString):
            stringType, string = CommonMethods.urlStripper(songString)
            if stringType != urlTypes.unknown:
                isCorrect = True
        else:
            stringType, string = urlTypes.name, CommonMethods.cleanedTrackName(songString.strip())
            isCorrect = True
        return isCorrect, stringType, string


class CustomErrors:
    class noResultYTDLP(Exception):
        pass


class Tables:
    class guildSettings(Enum):
        selfName = "guild_settings"
        botID = "bot_id"
        guildID = "guild_id"
        volume = "volume"
        textChannelID = "text_channel_id"
        voiceChannelID = "voice_channel_id"
    class lastData(Enum):
        selfName = "last_data"
        offset = "offset"
        genre = "genre"
        fetchingYear = "fetching_year"
        fetched = "fetched"
    class lyricsDara(Enum):
        selfName = "lyrics_data"
        songID = "_id"
        lyrics = "lyrics"
    class newSpotifyURLS(Enum):
        selfName = "new_spotify_urls"
        url = "url"
        genre = "genre"
        year = "year"
        fetched = "fetched"
    class otherNames(Enum):
        selfName = "other_names"
        songID = "_id"
        songName = "name"
    class repeatID(Enum):
        selfName = "repeat_id"
        newID = "new_id"
        realID = "real_id"
        createdAt = "created_at"
    class requestCookies(Enum):
        selfName = "request_cookies"
        accountID = "id"
        value = "value"
        working = "working"
        password = "password"
    class requestorData(Enum):
        selfName = "requestor_data"
        songID = "_id"
        requestorID = "person"
    class searchData(Enum):
        selfName = "search_data"
        songID = "_id"
        realName = "real_name"
        spotify = "spotify"
        youtube = "yt"
    class songData(Enum):
        selfName = "song_data"
        songID = "_id"
        duration = "duration"
        thumbnail = "thumbnail"
        audioURL = "audio_url"
        audioURLCreatedAt = "audio_url_created_at"
    class spotifyAPIS(Enum):
        selfName = "spotify_apis"
        clientID = "client_id"
        secret = "secret"
        owner = "owner"
