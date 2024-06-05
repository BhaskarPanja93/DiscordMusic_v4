from internal.Enum import RequiredFiles
from autoReRun import Runner

toRun = {RequiredFiles.storageRunnable.value: []}
toCheck = RequiredFiles.botRequired.value
interval = 2


Runner(toRun, toCheck, interval).start()
