# -*- coding: utf-8 -*-
"""歌单导入导出：JSON / CSV / TXT"""
import csv
import json
from pathlib import Path

from app.core.models import Song


def import_songs(filepath: str) -> list:
    """从文件导入歌曲列表，过滤无效条目"""
    ext = Path(filepath).suffix.lower()
    songs = []
    with open(filepath, "r", encoding="utf-8-sig") as f:
        if ext == ".json":
            data = json.load(f)
            items = data if isinstance(data, list) else data.get("songs", [])
            for it in items:
                songs.append(Song(
                    id=str(it.get("id", "")).strip(),
                    name=str(it.get("name", "")).strip(),
                    artist=str(it.get("artist", "")).strip(),
                    album=str(it.get("album", "")).strip(),
                ))
        elif ext == ".csv":
            reader = csv.reader(f)
            for row in reader:
                if len(row) >= 3:
                    songs.append(Song(id=row[2].strip(), name=row[0].strip(), artist=row[1].strip()))
                elif len(row) == 2:
                    songs.append(Song(id=row[1].strip(), name=row[0].strip()))
        else:  # txt：每行 name,artist,id 或 name,id
            for line in f:
                parts = line.strip().split(",")
                if len(parts) >= 3:
                    songs.append(Song(name=parts[0].strip(), artist=parts[1].strip(), id=parts[2].strip()))
                elif len(parts) == 2:
                    songs.append(Song(name=parts[0].strip(), id=parts[1].strip()))
    return [s for s in songs if s.name and s.id.isdigit()]


def export_songs(songs: list, filepath: str) -> None:
    """将歌曲列表导出为 JSON / CSV / TXT"""
    ext = Path(filepath).suffix.lower()
    with open(filepath, "w", encoding="utf-8-sig") as f:
        if ext == ".json":
            json.dump([{"name": s.name, "artist": s.artist, "album": s.album,
                        "id": s.id, "duration_ms": s.duration_ms} for s in songs],
                      f, ensure_ascii=False, indent=2)
        elif ext == ".csv":
            writer = csv.writer(f)
            for s in songs:
                writer.writerow([s.name, s.artist, s.id])
        else:
            for s in songs:
                f.write(f"{s.name},{s.artist},{s.id}\n")
