from glob import glob

from setuptools import setup

package_name = "rodeo_agent"

setup(
    name=package_name,
    version="0.1.0",
    packages=[package_name],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        ("share/" + package_name + "/launch", glob("launch/*.launch.py")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Tersoo Samuel Awai",
    maintainer_email="samuel.awai5@gmail.com",
    description="RODEO robot agent",
    license="MIT",
    entry_points={
        "console_scripts": [
            "agent = rodeo_agent.agent_node:main",
            "fake_executor = rodeo_agent.fake_executor:main",
            "station_executor = rodeo_agent.station_executor:main",
        ],
    },
)
