from sys import argv
from threading import Thread

from customisedLogs import Manager as LogManager
from discord import Intents, Guild, Status, Game, Interaction, User, Message, TextChannel

from Enum import Decorators, Constants, CommonMethods
from GuildManager import ManagedGuild
from ModifiedBot import ModifiedAutoShardedBot

#httpPool = httpPoolManager(num_pools=200, ca_certs=where(), timeout=Timeout(connect=2, read=8))
mysqlPool = CommonMethods.connectMySQL()
logger = LogManager()
guildManagers:dict[Guild, ManagedGuild] = {}
takeOvers: dict[int, list[TextChannel | bool]] = {}
try:
    token, prefix = argv[1], argv[2]
except:
    token, prefix = "", ""
    logger.fatal("No arguments for token and prefix")
    input("")
botObj = ModifiedAutoShardedBot(command_prefix=prefix, case_insensitive=True, intents=Intents().all(), strip_after_prefix=True)


@botObj.event
async def on_ready():
    """
    Executed when the bot has logged in and ready to work.
    """
    logger.success("LOGIN", f'Logged in (ID: {botObj.user.id}) as {botObj.user}')
    await botObj.change_presence(status=Status.dnd, activity=Game(name="This Game"))
    for guild in botObj.guilds:
        Thread(target=activateGuild, args=(guild,)).start()


@botObj.event
async def on_guild_join(guild:Guild):
    """
    Executed when the bot joins a new guild.
    :param guild: The Guild object of the guild that the bot joined
    """
    logger.success("GUILD", f'New Guild (ID: {guild.id}) {guild.name}')
    Thread(target=activateGuild, args=(guild,)).start()


@botObj.event
async def on_guild_remove(guild:Guild):
    """
    Executed when the bot joins a new guild.
    :param guild: The Guild object of the guild that the bot joined
    """
    logger.failed("GUILD", f'Removed (ID: {guild.id}) {guild.name}')
    await guildManagers[guild].stopOperation()


@botObj.event
async def on_message(message: Message):
    if message.guild is None:
        if message.author.id is not botObj.user.id:
            if message.author.id in takeOvers:
                anonymous = takeOvers[message.author.id][1]
                if anonymous: await takeOvers[message.author.id][0].send(message.content)
                else: await takeOvers[message.author.id][0].send(f"{message.author.mention}: {message.content}")
            else: await message.channel.send("TakeOver is off")


def activateGuild(guild:Guild)->None:
    """
    Starts all guild operations here.
    :param guild: Guild object of the individual guild
    """
    manager = ManagedGuild(botObj, guild, mysqlPool, logger)
    guildManagers[guild] = manager
    botObj.loop.create_task(manager.importSettings())
    botObj.tree.copy_global_to(guild=guild)
    botObj.loop.create_task(botObj.tree.sync(guild=guild))
    logger.success("COMMANDS", f"Synced for Guild (ID: {guild.id}) {guild.name}")
    try:
        if guild.me.nick is None:
           botObj.loop.create_task(guild.me.edit(nick=Constants.defaultBotNickName.value))
           logger.success("NICKNAME", f"Default Guild (ID: {guild.id}) {guild.name}")
        logger.success("NICKNAME", f"Custom Guild (ID: {guild.id}) {guild.name}")
    except Exception as e:
        logger.failed("NICKNAME", f"Cant change nickname Guild (ID: {guild.id}) {guild.name}")


@botObj.tree.command(name="login", description="Bind the bot to a Text Channel")
@Decorators.isGuildOwner()
async def _login(interaction:Interaction):
    logger.info("COMMAND-RECV", f"login (ID: {interaction.guild.id}) {interaction.guild.name}")
    channel = interaction.channel
    await guildManagers[interaction.guild].updateTextChannel(channel)
    await interaction.response.defer(thinking=False)
    await interaction.delete_original_response()
    logger.info("COMMAND-RECV", f"login executed Guild (ID: {interaction.guild.id}) {interaction.guild.name}")


@botObj.tree.command(name="errors", description="Register channel to send bot errors")
@Decorators.isBotOwner()
async def _errors(interaction:Interaction):
    logger.info("COMMAND-RECV", f"errors (ID: {interaction.guild.id}) {interaction.guild.name}")
    await interaction.response.defer(thinking=False)
    await interaction.delete_original_response()
    logger.info("COMMAND-RECV", f"errors executed Guild (ID: {interaction.guild.id}) {interaction.guild.name}")


@botObj.tree.command(name="nickname", description="Change bot nickname")
@Decorators.isGuildOwner()
async def _nickname(interaction:Interaction, new_nickname:str):
    logger.info("COMMAND-RECV", f"nickname (ID: {interaction.guild.id}) {interaction.guild.name}")
    await interaction.response.defer(thinking=False)
    await interaction.delete_original_response()
    status, reason = await guildManagers[interaction.guild].updateNick(new_nickname.strip())
    if status:
        await interaction.response.send_message(f"Nickname CHanged by {interaction.user.mention} ")
    else:
        await interaction.response.send_message("Bot doesnt have permission for nickname change! ")
    logger.info("COMMAND-RECV", f"nickname executed Guild (ID: {interaction.guild.id}) {interaction.guild.name}")


@botObj.tree.command(name="whisper", description="Pass message to someone via the bot")
async def _takeoverOn(interaction:Interaction, receiver:User, text:str):
    logger.info("COMMAND-RECV", f"say (ID: {interaction.guild.id}) {interaction.guild.name}")
    await interaction.channel.send(f"{receiver.mention}: {text}")
    logger.info("COMMAND-RECV", f"say executed Guild (ID: {interaction.guild.id}) {interaction.guild.name}")


@botObj.tree.command(name="takeover_on", description="Let the bot type for you")
async def _takeoverOn(interaction:Interaction, anonymous:bool):
    logger.info("COMMAND-RECV", f"takeover_on (ID: {interaction.guild.id}) {interaction.guild.name}")
    await interaction.response.send_message(f"Takeover enabled for {interaction.user.mention}", ephemeral=True, delete_after=20)
    takeOvers[interaction.user.id] = [interaction.channel, anonymous]
    logger.info("COMMAND-RECV", f"takeover_on executed Guild (ID: {interaction.guild.id}) {interaction.guild.name}")


@botObj.tree.command(name="takeover_off", description="Stop the bot from typing for you")
async def _takeoverOff(interaction:Interaction):
    logger.info("COMMAND-RECV", f"takeover_off (ID: {interaction.guild.id}) {interaction.guild.name}")
    if interaction.user.id in takeOvers:
        del takeOvers[interaction.user.id]
        await interaction.response.send_message(f"Takeover disabled for {interaction.user.mention}", ephemeral=True, delete_after=20)
    logger.info("COMMAND-RECV", f"takeover_off executed Guild (ID: {interaction.guild.id}) {interaction.guild.name}")


@botObj.tree.command(name="clear", description="Delete messages from current channel, give count, or 0 to delete all.")
async def _clear(interaction:Interaction):
    logger.info("COMMAND-RECV", f"clear (ID: {interaction.guild.id}) {interaction.guild.name}")
    await interaction.response.defer(thinking=False)
    await interaction.delete_original_response()
    await guildManagers[interaction.guild].deleteChannelTexts(interaction.channel, 0)
    logger.info("COMMAND-RECV", f"clear executed Guild (ID: {interaction.guild.id}) {interaction.guild.name}")


@botObj.tree.command(name="play", description="Play from name or link or a playlist")
async def _play(interaction:Interaction, song:str):
    logger.info("COMMAND-RECV", f"play (ID: {interaction.guild.id}) {interaction.guild.name}")
    voiceChannel = interaction.user.voice.channel
    status, reason = await guildManagers[interaction.guild].songPlayer.receiveSongStringFromUser(song, voiceChannel)
    if status:
        await interaction.response.send_message(content=f"{interaction.user.mention} Added to queue", ephemeral=False, delete_after=20)
        logger.info("COMMAND-RECV", f"play executed Guild (ID: {interaction.guild.id}) {interaction.guild.name}")
    else:
        await interaction.response.send_message(content=f"{interaction.user.mention} Failed to add song because {reason}", ephemeral=False, delete_after=20)
        logger.failed("COMMAND-RECV", f"play failed Guild (ID: {interaction.guild.id}) {interaction.guild.name}")


if __name__ == "__main__":
    botObj.run(token, reconnect=True)
