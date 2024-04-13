from asyncio import sleep as asyncSleep
from datetime import datetime, timezone
from customisedLogs import Manager as LogManager
from discord import Guild, TextChannel, Message, Forbidden, VoiceChannel
from pooledMySQL import Manager as MySQLManager

from ModifiedBot import ModifiedAutoShardedBot
from SongManager import SongManager


class ManagedGuild:
    def __init__(self, botObj:ModifiedAutoShardedBot, guildObj:Guild, mySQLPool:MySQLManager, logger:LogManager):
        self.botObj = botObj
        self.guildObj = guildObj
        self.mySQLPool = mySQLPool
        self.logger = logger

        self.textChannelID:int = 0
        self.textChannel:None|TextChannel = None
        self.voiceChannelID:int = 0
        self.voiceChannel:None|VoiceChannel = None

        self.lyricMsg:None|Message = None
        self.panelMsg:None|Message = None

        self.songPlayer = SongManager(botObj, guildObj, self, mySQLPool, logger)

        logger.success("ACTIVE", f'Server: (ID: {self.guildObj.id}) {self.guildObj.name}')


    async def importSettings(self):
        result = self.mySQLPool.execute(f"SELECT * from guild_settings where guild_id=\"{self.guildObj.id}\" and bot_id=\"{self.botObj.application_id}\"")
        if len(result):
            resultTup = result[0]
            volume = resultTup[2]
            textChannelID = int(resultTup[3])
            voiceChannelID = int(resultTup[4])
            allChannels = await self.guildObj.fetch_channels()
            for channel in allChannels:
                if channel.id == textChannelID != 0:
                    self.textChannel = channel
                if channel.id == voiceChannelID != 0:
                    self.voiceChannel = channel
            self.songPlayer.setVolume(volume)

        else:
            self.mySQLPool.execute(f"INSERT into guild_settings values("
                                   f"\"{self.botObj.application_id}\", "
                                   f"\"{self.guildObj.id}\", "
                                   f"{self.songPlayer.volume}, "
                                   f"\"{self.textChannelID}\", "
                                   f"\"{self.voiceChannelID}\")")
        if self.textChannel is not None:
            await self.deleteChannelTexts(self.textChannel, 0, True)
            await self.sendLyric()
            await self.sendPanel()
        self.logger.success("IMPORT-SETTINGS", f"Complete (ID: {self.guildObj.id}) {self.guildObj.name}")


    async def stopOperation(self):
        pass


    async def sendLyric(self):
        pass


    async def sendPanel(self):
        pass


    async def deleteChannelTexts(self, channel:TextChannel, count:int=0, deleteImportant:bool=True):
        self.logger.skip("DEL-CHANNEL-TEXTS", f"(ID: {self.guildObj.id}) {self.guildObj.name}")
        delAll = False
        if count == 0:
            delAll = True
        while count or delAll:
            _count = min(100, count if not delAll else 100)
            count -= _count
            msgs = [entry async for entry in channel.history(limit=_count, oldest_first=False)]
            if not len(msgs):
                break
            if not deleteImportant:
                if self.lyricMsg is not None and self.lyricMsg in msgs:
                    msgs.remove(self.lyricMsg)
                if self.panelMsg is not None and self.panelMsg in msgs:
                    msgs.remove(self.panelMsg)
            await self.__deleteMsg(msgs)
        self.logger.success("DEL-CHANNEL-TEXTS", f"Deleted (ID: {self.guildObj.id}) {self.guildObj.name}")


    async def __deleteMsg(self, message: list[Message] | Message, delay: float = 0) -> None:
        await asyncSleep(delay)
        self.logger.skip("DEL-RAW-TEXTS", f"(ID: {self.guildObj.id}) {self.guildObj.name}")
        if type(message) != list:
            message = [message]
        mass_delete_list = []
        while True:
            if not message or len(mass_delete_list) >= 100:
                if mass_delete_list:
                    try:
                        await mass_delete_list[0].channel.delete_messages(mass_delete_list)
                        self.logger.success("DEL-RAW-TEXTS", f"Deleted {len(mass_delete_list)}")
                        mass_delete_list = []
                    except Forbidden:
                        self.logger.failed("DEL-RAW-TEXTS", f"Not enough permissions (ID: {self.guildObj.id}) {self.guildObj.name}")
                if not message:
                    break
            else:
                msgObj = message.pop()
                if (datetime.now(timezone.utc) - msgObj.created_at.astimezone(timezone.utc)).days < 14:
                    mass_delete_list.append(msgObj)
                else:
                    await self.__deleteMsg(msgObj)


    async def updateTextChannel(self, channel:TextChannel):
        try:
            old = self.textChannel
            self.textChannelID = channel.id
            self.textChannel = await self.guildObj.fetch_channel(self.textChannelID)
            self.mySQLPool.execute(f"UPDATE guild_settings set text_channel_id=\"{self.textChannelID}\" where guild_id=\"{self.guildObj.id}\" and bot_id=\"{self.botObj.user.id}\"")
            self.logger.success("TEXT-CHANNEL", f"Updated {old}->{self.textChannel} (ID: {self.guildObj.id}) {self.guildObj.name}")
            return True, ""
        except Exception as e:
            return False, repr(e)


    async def updateNick(self, newNickName:str):
        try:
            old = self.guildObj.me.nick
            await self.guildObj.me.edit(nick=newNickName)
            self.logger.success("TEXT-CHANNEL", f"Updated {old}->{newNickName} (ID: {self.guildObj.id}) {self.guildObj.name}")
            return True, ""
        except Forbidden:
            self.logger.failed("NICK", f"Nickname Change Failed : Not enough permissions")
            return False, "Not enough Permissions"


    async def joinVC(self, channel:VoiceChannel):
        await self.disconnectVC()
        self.logger.info("VC", f"Joining {channel} (ID: {self.guildObj.id}) {self.guildObj.name}")
        await channel.connect(self_deaf=True, reconnect=True)
        self.logger.success("VC", f"Joined {channel} (ID: {self.guildObj.id}) {self.guildObj.name}")


    async def disconnectVC(self):
        if self.guildObj.voice_client:
            self.logger.info("VC", f"Leaving {self.guildObj.voice_client.channel} (ID: {self.guildObj.id}) {self.guildObj.name}")
            await self.guildObj.voice_client.disconnect(force=True)
            if self.guildObj.voice_client is not None:
                self.guildObj.voice_client.cleanup()
            self.logger.success("VC", f"Left (ID: {self.guildObj.id}) {self.guildObj.name}")

