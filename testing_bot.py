from autoReRun import Runner
from internal.SecretEnum import BotToken, BotPrefix
from internal.Enum import RequiredFiles


toRun = {RequiredFiles.botRunnable.value: [BotToken.angel.value, BotPrefix.angel.value]}
toCheck = RequiredFiles.botRequired.value
interval = 2


Runner(toRun,  toCheck, interval).start()
