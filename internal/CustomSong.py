class Song:
    def __init__(self):
        self.ID = ""
        self.requestor = ""
        self.name = ""
        self.allyName = ""
        self.yt = ""
        self.spotify = ""
        self.duration = 0
        self.audioURL = ""
        self.thumbnail = ""
        self.expiry = None
        self.lyrics = "no lyrics lol"


    def jsonify(self):
        return {
            "id":self.ID,
            "name":self.name,
            "yt":self.yt,
            "spotify":self.spotify,
            "duration":self.duration,
            "audioURL":self.audioURL,
            "thumbnail":self.thumbnail,
            "expiry":self.expiry,
            "lyrics":self.lyrics
        }


    def readDict(self, source:dict):
        self.ID = source.get("id")
        self.name = source.get("name")
        self.yt = source.get("yt")
        self.spotify = source.get("spotify")
        self.duration = float(source.get("duration"))
        self.audioURL = source.get("audioURL")
        self.thumbnail = source.get("thumbnail")
        self.expiry = source.get("expiry")
        self.lyrics = source.get("lyrics")


