class InstallerError(Exception):
    """Base exception for installer errors."""


class DownloadError(InstallerError):
    def __init__(self, url: str, reason: str = ""):
        self.url = url
        self.reason = reason
        message = f"Failed to download {url}"
        if reason:
            message = f"{message}: {reason}"
        super().__init__(message)


class ScriptExecutionError(InstallerError):
    def __init__(self, script_name: str, reason: str = ""):
        self.script_name = script_name
        self.reason = reason
        message = f"Script execution failed: {script_name}"
        if reason:
            message = f"{message}: {reason}"
        super().__init__(message)


class PackageInstallError(InstallerError):
    def __init__(self, package: str, reason: str = ""):
        self.package = package
        self.reason = reason
        message = f"Failed to install {package}"
        if reason:
            message = f"{message}: {reason}"
        super().__init__(message)


class ExecutableNotFoundError(InstallerError):
    def __init__(self, executable: str):
        self.executable = executable
        super().__init__(f"Required executable not found: {executable}")
