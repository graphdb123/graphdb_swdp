import setuptools

setuptools.setup(
    name="odoo-upgrade-automation",
    version="0.0.1",
    author="CGI",
    author_email="priyanka.panda@cgi.com",
    description="Tools to migrate Odoo modules from a version" " to another",
    long_description=open("README.rst").read(),
    long_description_content_type="text/x-rst",
    packages=["odoo_module_upgrade", "odoo_module_upgrade.upgrade_scripts"],
    include_package_data=True,
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Framework :: Odoo",
    ],
    install_requires=open("requirements.txt").read().splitlines(),
    entry_points=dict(
        console_scripts=[
            "odoo-module-upgrade=odoo_module_upgrade.__main__:main",
        ]
    ),
    keywords=[
        "Odoo Community Association (OCA)",
        "Odoo",
        "Migration",
        "Upgrade",
        "Module",
    ],
)
