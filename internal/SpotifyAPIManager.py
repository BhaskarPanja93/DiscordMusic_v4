from time import time, sleep

from spotipy import Spotify,SpotifyClientCredentials, CacheFileHandler

class RateLimitedSpotify(Spotify):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.waitTime = 1
        self.requests_timeout = 10
        self.last_used = time()
        self.queue = []

    def limited(self, _id):
        self.queue.append(_id)
        while time() - self.last_used < self.waitTime or self.queue[0] != _id:
            sleep(1)
        self.queue.pop(0)
        self.last_used = time()
