#!/usr/bin/env python3
"""
Package a release: dist/KweetchenKaos-<version>.zip, holding the mod folder
(Chromecide_KweetchenKaos/) ready to drop into a server's mods/ folder.

    python3 release.py            build, zip, and BOOT the zip on your server to prove the game
                                  takes it (then your normal build goes back on)
    python3 release.py --no-boot  build and zip only

The version is settings.VERSION (build/settings.py). A release build leaves out this project's
own authoring data -- the plot saves and /kk restore -- which are the author's working copies,
not the game; the authoring world and its tools stay in.

WHY IT BOOTS: a release once shipped that its own server couldn't load, because the dev server
never saw the packaged files. So the zip is unpacked and installed exactly as a user would, the
server started, and its log checked, before anything is published. Needs a server with run.sh
(see deploy.py); without one, install the zip by hand and check before publishing.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "build"))
import settings  # noqa: E402
import deploy  # noqa: E402

DIST = os.path.join(HERE, "dist")


def build_release():
    code = subprocess.run([sys.executable, os.path.join(HERE, "build", "build.py"), "--release"],
                          capture_output=True, text=True)
    if code.returncode:
        print(code.stdout + code.stderr)
        sys.exit("the release build failed")
    print(code.stdout.rstrip().splitlines()[-1] if code.stdout.strip() else "built")


def zip_pack():
    os.makedirs(DIST, exist_ok=True)
    path = os.path.join(DIST, f"{settings.PACK_NAME}-{settings.VERSION}.zip")
    folder = deploy.MOD
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk(settings.PACK):
            for f in files:
                full = os.path.join(root, f)
                z.write(full, os.path.join(folder, os.path.relpath(full, settings.PACK)))
    print(f"wrote {os.path.relpath(path, HERE)} ({os.path.getsize(path) // 1024} KB)")
    return path


def boot(zip_path):
    """Install the ZIP's contents (not pack/) as a user would, start the server, read its log."""
    server = settings.SERVER
    run = os.path.join(server or "", "run.sh")
    if not server or not os.access(run, os.X_OK):
        print("No run.sh in the server folder: install the zip by hand and check the server log "
              "before publishing.")
        return
    if deploy.port_taken():
        deploy.stop_server()
    unpacked = tempfile.mkdtemp()
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(unpacked)
    installed = os.path.join(server, "mods", deploy.MOD)
    deploy.install(server)          # rescues layout saves first, then installs pack/ ...
    shutil.rmtree(installed)        # ... which is replaced by what the ZIP holds
    shutil.copytree(os.path.join(unpacked, deploy.MOD), installed)
    shutil.rmtree(unpacked)
    started = subprocess.run([run], cwd=server, capture_output=True, text=True)
    print((started.stdout.strip().splitlines() or [""])[-1])
    print("booted the release zip:")
    deploy.check_log(server)


def main(argv):
    build_release()
    path = zip_pack()
    if "--no-boot" not in argv:
        boot(path)
        print("putting your normal build back...")
        subprocess.run([sys.executable, os.path.join(HERE, "deploy.py")], capture_output=True)
    print(f"release {settings.VERSION}: {os.path.relpath(path, HERE)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
