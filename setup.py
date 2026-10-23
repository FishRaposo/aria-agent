"""Build-only copies of canonical shared skills into installed package resources."""

from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py


class BuildWithSkills(build_py):
    def run(self):
        super().run()
        source = Path(__file__).resolve().parent / ".agents" / "skills"
        for skill in sorted(source.glob("*/SKILL.md")):
            destination = Path(self.build_lib) / "aria" / "_skills" / skill.parent.name
            destination.mkdir(parents=True, exist_ok=True)
            self.copy_file(str(skill), str(destination / "SKILL.md"))


setup(cmdclass={"build_py": BuildWithSkills})
