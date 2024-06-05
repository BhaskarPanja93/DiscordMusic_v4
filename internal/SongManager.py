from asyncio import sleep
from time import time
from aiohttp import ClientSession
from discord import Guild, VoiceChannel, FFmpegPCMAudio, PCMVolumeTransformer
from pooledMySQL import Manager as MySQLManager
from customisedLogs import Manager as LogManager

from ModifiedBot import ModifiedAutoShardedBot
from Enum import CommonMethods, errorCodes, urlTypes, storageRoutes, Constants
from CustomSong import Song


class SongManager:
    def __init__(self, botObj:ModifiedAutoShardedBot, guildObj:Guild, GuildManager, mySQLPool:MySQLManager, logger:LogManager):
        self.botObj = botObj
        self.guildObj = guildObj
        self.GuildManager = GuildManager
        self.mySQLPool = mySQLPool
        self.logger = logger

        self.started = False
        self.volume = 100
        self.paused = False
        self.loopEnabled = True
        self.currentIndex = 0

        self.queue:list[Song] = []


    def setVolume(self, newValue:int):
        old = self.volume
        self.volume = newValue
        self.logger.success("VOLUME", f"Changed {old}->{self.volume} (ID: {self.guildObj.id}) {self.guildObj.name}")
        if self.guildObj.voice_client is not None:
            old = self.guildObj.voice_client.source.volume
            self.guildObj.voice_client.source.volume = self.volume / 100
            self.logger.success("VOLUME", f"VoiceClient {old}->{self.guildObj.voice_client.source.volume} (ID: {self.guildObj.id}) {self.guildObj.name}")


    async def receiveSongStringFromUser(self, string:str, voiceChannel: VoiceChannel | None):
        if self.GuildManager.textChannel is None:
            self.logger.failed("PLAY", f"Channel not registered (ID: {self.guildObj.id}) {self.guildObj.name}")
            return False, errorCodes.botNotLoggedIn.value
        else:
            if not voiceChannel:
                self.logger.failed("PLAY", f"User not in VC (ID: {self.guildObj.id}) {self.guildObj.name}")
                return False, errorCodes.userNotInVC.value
            else:
                isCorrect, stringType, string = CommonMethods.songStringIdentifier(string)
                if not isCorrect:
                    self.logger.failed("PLAY", f"Invalid song string (ID: {self.guildObj.id}) {self.guildObj.name}")
                    return False, errorCodes.invalidSongString.value
                else:
                    if not self.started or not self.guildObj.voice_client or (self.guildObj.voice_client.channel != voiceChannel and (self.paused or time() - self.paused > 60)):
                        self.logger.info("PLAY", f"Switching channel to {voiceChannel} (ID: {self.guildObj.id}) {self.guildObj.name}")
                        await self.GuildManager.joinVC(voiceChannel)
                    else:
                        self.logger.failed("PLAY", f"Bot Busy {self.guildObj.voice_client.channel} (ID: {self.guildObj.id}) {self.guildObj.name}")
                        return False, errorCodes.botPlayingInDifferentChannel.value
                    self.logger.success("PLAY", f"Received {stringType.value} {string} (ID: {self.guildObj.id}) {self.guildObj.name}")
                    if stringType in [urlTypes.spotify_album, urlTypes.spotify_playlist, urlTypes.spotify_artist, urlTypes.youtube_playlist]:
                        await self.fetchPlayListSongID(stringType.value, string)
                    else:
                        await self.fetchIndividualSongID(string)
                    return True, ""


    def __changeIndex(self, *args, **kwargs):
        if self.currentIndex < len(self.queue) and not self.loopEnabled:
            self.currentIndex += 1
        self.botObj.loop.create_task(self.__nextSong())


    async def __nextSong(self):
        self.logger.info("NEXT-SONG", f"Triggered (ID: {self.guildObj.id}) {self.guildObj.name}")
        self.guildObj.voice_client.stop()
        if self.currentIndex < len(self.queue):
            songID = self.queue[self.currentIndex].ID
            url = f"http://127.0.0.1:{Constants.storagePort.value}{storageRoutes.requestData.value}"
            data = {"id": songID}
            try:
                async with ClientSession() as session:
                    async with session.post(url, data=data, timeout=15) as response:
                        response.raise_for_status()
                        r = await response.json()
                        self.logger.info("SONG-DATA", f"Fetched (ID: {self.guildObj.id}) {self.guildObj.name}")
            except:
                await sleep(0.5)
            if self.queue[self.currentIndex].ID == songID:
                self.queue[self.currentIndex].readDict(r)
            player = FFmpegPCMAudio(self.queue[self.currentIndex].audioURL, before_options='-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 1', executable="binaries/ffmpeg.exe")
            self.guildObj.voice_client.play(player, after=self.__changeIndex)
            self.guildObj.voice_client.source = PCMVolumeTransformer(self.guildObj.voice_client.source)
            self.guildObj.voice_client.source.volume = self.volume / 100
        #await self.sendLyric()
        #await self.sendPanel()
        self.logger.success("NEXT-SONG", f"End (ID: {self.guildObj.id}) {self.guildObj.name}")


    async def __addToQueue(self, song:Song, indexToPut:int=-1):
        if indexToPut == -1 or len(self.queue)<=indexToPut and self.currentIndex!=indexToPut:
            self.queue.append(song)
        else:
            self.queue.insert(indexToPut, song)
        self.logger.success("NEW-SONG", f"Added Length:{len(self.queue)} (ID: {self.guildObj.id}) {self.guildObj.name}")
        if self.currentIndex+1 == len(self.queue):
            await self.__nextSong()


    async def fetchIndividualSongID(self, string:str):
        url = f"http://127.0.0.1:{Constants.storagePort.value}{storageRoutes.requestID.value}"
        data = {"string": string, "priority": 1}
        while True:
            try:
                async with ClientSession() as session:
                    async with session.post(url, data=data, timeout=10) as response:
                        response.raise_for_status()
                        r = await response.json(content_type=None)
                        break
            except:
                await sleep(1)
        song = Song()
        song.ID = r.get("songID")
        await self.__addToQueue(song)
        self.logger.success("STORAGE-REQ-SONG", f"Received {song.ID} (ID: {self.guildObj.id}) {self.guildObj.name}")


    async def fetchPlayListSongID(self, stringType:urlTypes, string:str):
        url = f"http://127.0.0.1:{Constants.storagePort.value}{storageRoutes.extractPlayList.value}"
        data = {"type": stringType, "string": string, "priority": 1}
        while True:
            try:
                async with ClientSession() as session:
                    async with session.post(url, data=data, timeout=10) as response:
                        response.raise_for_status()
                        r = await response.json(content_type=None)
                        break
            except:
                await sleep(1)
        for songID in r:
            song = Song()
            song.ID = songID
            await self.__addToQueue(song)
        self.logger.success("STORAGE-REQ-PL", f"Received Count:{len(r)} (ID: {self.guildObj.id}) {self.guildObj.name}")
