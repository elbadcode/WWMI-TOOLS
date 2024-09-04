import os
import re
from dataclasses import dataclass
from pathlib import Path
import subprocess


@dataclass
class Texture:
    hash: str
    path: Path
    filename: str


def get_textures(object_source_folder: Path):
    textures = {}
    # scandir is many times faster than listdir and is standard now
    for texfile in os.scandir(object_source_folder):
        # I don't think I would use python if not for tuples and walrus operator
        if (texname := texfile.name.lower()).endswith(
            (".dds", ".jpg", ".png", ".tga", ".jpeg", ".tiff", 'tif')
        ):
            hash_pattern = re.compile(r".*t=([a-f0-9]{8}).*")
            result = hash_pattern.findall(texname)
            if len(result) != 1:
                # Handle old format
                hash_pattern = re.compile(r".*component_\d-ps-t\d-([a-f0-9]{8}).*")
                result = hash_pattern.findall(texname)
                if len(result) != 1:
                    continue
            texture_hash = result[0]
            # not sure yet how to query other blender addons but ideally should just pass this off to dds addon
            # blender sucks for dds workflow its generally best to work with uncompressed textures and convert after
            if not texname.endswith(".dds"):
                try:
                    if "texconv" in os.environ["Path"]:
                        texconv = subprocess.run(
                            args=[
                                "texconv",
                                texfile.path,
                                "-o",
                                texfile.path,
                                "-y",
                                "-ft",
                                "dds",
                            ],
                            executable="C:/Windows/System32/cmd.exe",
                            shell=True,
                        )
                    elif tconv := os.environ["texconv"] is not None:
                        if tconv.endswith(".exe"):
                            texconv = subprocess.run(
                                args=[
                                    texfile.path,
                                    "-o",
                                    texfile.path,
                                    "-y",
                                    "-ft",
                                    "dds",
                                ],
                                executable=tconv,
                                shell=True,
                            )
                        elif os.path.isdir(tconv):
                            pass
                except Exception as e:
                    print(e)
                texname = os.path.splitext(texname)[0] + ".dds"
            textures[texture_hash] = Texture(
                hash=texture_hash,
                # usually I pass only the file entry since you can access path or name from a single var,
                # but there's no harm done unless we have lots of variables to remember and you got to meet the walrus
                path=Path(texfile.path),
                filename=texname,
            )

    return list(textures.values())
