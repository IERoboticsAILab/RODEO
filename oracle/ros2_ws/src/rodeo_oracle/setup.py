from glob import glob

from setuptools import setup

package_name = "rodeo_oracle"

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
    description="RODEO oracle as ROS 2 nodes",
    license="MIT",
    entry_points={
        "console_scripts": [
            "oracle = rodeo_oracle.oracle:main",
            "delivery_validator = rodeo_oracle.delivery_validator:main",
            "charging_validator = rodeo_oracle.charging_validator:main",
        ],
    },
)
