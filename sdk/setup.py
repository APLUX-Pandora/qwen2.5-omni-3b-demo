from pathlib import Path
import shutil

from setuptools import Distribution, setup
from setuptools.command.build_py import build_py
from wheel.bdist_wheel import bdist_wheel


class Build(build_py):
    def run(self):
        library_dir = Path(__file__).resolve().parent / "lib"
        library = library_dir / "libqwen25_omni.so"
        if not library.is_file():
            raise RuntimeError("Matching precompiled native library is required")
        header = library.read_bytes()[:20]
        if header[:6] != b"\x7fELF\x02\x01" or int.from_bytes(header[18:20], "little") != 183:
            raise RuntimeError("Expected Linux AArch64 native library")
        # Reused build directories must not retain withdrawn public modules.
        for name in ("qwen25_omni", "pandora_qwen25_omni"):
            package_dir = Path(self.build_lib) / name
            if package_dir.exists():
                shutil.rmtree(package_dir)
        super().run()
        destination = Path(self.build_lib) / "pandora_qwen25_omni" / "lib"
        destination.mkdir(parents=True, exist_ok=True)
        for name in ("libqwen25_omni.so", "LICENSE"):
            shutil.copyfile(library_dir / name, destination / name)
        shutil.copytree(library_dir / "qnn248", destination / "qnn248")

    def get_outputs(self, include_bytecode=1):
        outputs = super().get_outputs(include_bytecode)
        destination = Path(self.build_lib) / "pandora_qwen25_omni" / "lib"
        library_dir = Path(__file__).resolve().parent / "lib"
        return outputs + [
            str(destination / source.relative_to(library_dir))
            for source in library_dir.rglob("*") if source.is_file()
        ]


class BinaryDistribution(Distribution):
    def has_ext_modules(self):
        return True


class PlatformWheel(bdist_wheel):
    def get_tag(self):
        # The supplied library is Linux AArch64 even when packaging on another host.
        return "py3", "none", "linux_aarch64"


setup(distclass=BinaryDistribution, cmdclass={"build_py": Build, "bdist_wheel": PlatformWheel})
