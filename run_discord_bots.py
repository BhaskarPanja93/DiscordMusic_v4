from autoReRun import Runner
from internal.SecretEnum import BotToken, BotPrefix
from internal.Enum import RequiredFiles

toCheck = RequiredFiles.botRequired.value
interval = 2

toRun = {RequiredFiles.botRunnable.value: [BotToken.angel.value, BotPrefix.angel.value]}
Runner(toRun, toCheck, interval).start()

toRun = {RequiredFiles.botRunnable.value: [BotToken.test.value, BotPrefix.test.value]}
Runner(toRun, toCheck, interval).start()
