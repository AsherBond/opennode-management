from zope.interface import Interface


class IJob(Interface):

    def run():
        pass

    def start_polling():
        pass


class IFuncInstalled(Interface):
    """Marker for FUNC-controlled Computes."""


class IFuncMinion(Interface):
    def hostname():
        """Return the hostname of the minion"""


class IBotoManageable(Interface):
    """Marker for Computes controlled through the boto library."""


class IGetComputeInfo(IJob):
    """Returns general information about a compute (os, architecture, devices, etc)."""


class IHostInterfaces(IJob):
    """Returns detailed info about host interfaces. hardware.info doesn't work on all archs."""


class IGetRoutes(IJob):
    """Returns route info"""


class IGetGuestMetrics(IJob):
    """Returns guest VM metrics."""


class IGetHostMetrics(IJob):
    """Returns host (PHY) metrics."""


class IGetDiskUsage(IJob):
    """Returns func disk usage."""


class IGetLocalTemplates(IJob):
    """Get local templates"""


class IGetVirtualizationContainers(IJob):
    """Get virtualization container provided by a compute"""


class IDeployVM(IJob):
    """Deploys a vm."""


class IUndeployVM(IJob):
    """Undeploys a vm."""


class IListVMS(IJob):
    """List vms"""


class IStartVM(IJob):
    """Starts a vm."""


class IShutdownVM(IJob):
    """Shuts down a vm."""


class IDestroyVM(IJob):
    """Destroys a vm."""


class ISuspendVM(IJob):
    """Suspends a vm."""


class IResumeVM(IJob):
    """Resumes a vm."""


class IRebootVM(IJob):
    """Reboots a vm."""


class IGetSignedCertificateNames(IJob):
    """Contact certmaster."""
