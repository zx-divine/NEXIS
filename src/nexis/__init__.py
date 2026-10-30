"""Engineering versions stay monotonic; public launch branding is independent."""

__version__ = "1.4.2"
PUBLIC_VERSION = "1.1.0"
PUBLIC_NAME = "Nexis v1"
RELEASE_CHANNEL = "development"
DISPLAY_VERSION = "v" + (__version__[:-2] if __version__.endswith(".0") else __version__) + " Development Candidate (build " + __version__ + ")"
MIN_WINDOWS_BUILD = 19045
