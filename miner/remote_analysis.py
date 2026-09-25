"""Remote source adapter for the existing VOD Longa algorithm."""
import hashlib
import json
import math
from pathlib import Path

from miner import analysis, long_vod, media, visual_activity, performance


class RemoteSource:
    def __init__(self, vod, provider, temporaries, check=lambda: None, progress=lambda *a: None, window=None):
        self.vod, self.provider, self.temp = vod, provider, temporaries
        self.check, self.progress, self.window = check, progress, window
        self.leases = {}

    def key(self):
        return hashlib.sha256(json.dumps(["remote-1", self.vod["url"], self.vod["duration"], long_vod.VERSION,
                                          long_vod.CONFIG["chunk"], visual_activity.VERSION, visual_activity.INTERVAL,
                                          visual_activity.WIDTH, visual_activity.HEIGHT, self.window]).encode()).hexdigest()[:20]

    def parts(self, duration):
        a, b = self.window or (0, duration)
        return [(a + start, a + end) for start, end in long_vod.chunks(b - a, long_vod.CONFIG["chunk"])]

    def acquire(self, start, end, stage, quality="analysis"):
        self.check()
        self.temp.space(end - start, quality)
        folder = self.temp.lease(self.vod["id"], start, end, stage, quality)
        self.leases[str(stage)] = folder
        media_path = folder / "media.mp4"
        ready = folder / "ready.json"
        if not ready.exists() or not media_path.is_file():
            if media_path.exists():
                # Failed transfers are not complete checkpoints. Preserve retry intent first.
                save = folder / "retry.json"
                analysis.save_json(save, {"start": start, "end": end, "reason": "transfer incomplete"})
                media_path.unlink()
            info = self.provider.download(self.vod["url"], media_path, start, end, quality, self.check, self.progress)
            analysis.save_json(ready, info)
        self.leases[str(stage)] = folder
        return folder, media_path

    def failed(self, checkpoint):
        # The durable error/checkpoint contains the range to recreate on retry.
        for stage, lease in list(self.leases.items()):
            if lease.exists():
                proof = Path(checkpoint).with_name(f"retry_{lease.name}.json")
                analysis.save_json(proof, {"retry": json.loads((lease / "lease.json").read_text(encoding="utf-8")),
                                          "checkpoint": json.loads(Path(checkpoint).read_text(encoding="utf-8"))})
                self.temp.commit(lease, proof)
                self.completed(stage, proof)
            self.leases.pop(stage, None)

    @performance.measure("remote_scan_total")
    def scan(self, start, end, folder, progress):
        lease, source = self.acquire(start, end, str(folder))
        info = media.probe(source)
        if info["has_audio"]:
            audio = lease / "audio.wav"
            with performance.measure("audio_decode"):
                media.extract_audio(source, audio, end - start)
            with performance.measure("energy"):
                energy = analysis.energy(audio, folder / "energy.json")
        else:
            energy = [0.0] * math.ceil(end - start)
        with performance.measure("visual"):
            values = visual_activity.sample(source, end - start, folder / "visual.json", progress)
        visual = [{**s, "time": s["time"] + start} for s in values]
        return {"energy": energy, "visual": visual}

    def audio(self, start, end, folder):
        lease, source = self.acquire(start, end, str(folder))
        audio = lease / "audio.wav"
        with performance.measure("audio_decode"):
            media.extract_audio(source, audio, end - start)
        return audio

    def completed(self, folder, checkpoint):
        lease = self.leases.pop(str(folder), None)
        if lease and lease.exists():
            self.temp.commit(lease, checkpoint)
        # Whisper's chunk WAVs are generated in this remote-owned namespace, never user files.
        folder = Path(folder).resolve()
        if folder.is_relative_to(self.temp.data / "campaigns") and "remote" in folder.parts and Path(checkpoint).is_file():
            for file in folder.rglob("*.wav"):
                if not file.is_symlink():
                    file.unlink()
