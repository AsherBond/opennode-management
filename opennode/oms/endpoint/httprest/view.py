from grokcore.component import context
from zope.component import queryAdapter

from opennode.oms.endpoint.httprest.base import HttpRestView, IHttpRestView
from opennode.oms.model.location import ILocation
from opennode.oms.model.model import Machines, Computes, Compute, OmsRoot, Templates
from opennode.oms.model.model.base import IContainer
from opennode.oms.model.model.hangar import Hangar
from opennode.oms.model.model.byname import ByNameContainer
from opennode.oms.model.model.symlink import follow_symlinks
from opennode.oms.model.model.filtrable import IFiltrable


class RootView(HttpRestView):
    context(OmsRoot)

    def render(self, request):
        return dict((name, ILocation(self.context[name]).get_url()) for name in self.context.listnames())


class ContainerView(HttpRestView):
    context(IContainer)

    def render(self, request):
        items = map(follow_symlinks, self.context.listcontent())

        q = request.args.get('q', [''])[0]
        q = q.decode('utf-8')

        if q:
            items = [item for item in items if IFiltrable(item).match(q)]

        return [IHttpRestView(item).render(request) for item in items if queryAdapter(item, IHttpRestView) and not self.blacklisted(item)]

    def blacklisted(self, item):
        return isinstance(item, ByNameContainer)


class MachinesView(ContainerView):
    context(Machines)

    def blacklisted(self, item):
        return super(MachinesView, self).blacklisted(item) or isinstance(item, Hangar)


class ComputeView(HttpRestView):
    context(Compute)

    def render(self, request):
        ret = {'id': self.context.__name__,
                'hostname': self.context.hostname,
                'ip_address': self.context.ip_address,
                'url': ILocation(self.context).get_url(),
                'type': self.context.type,
                'features': [i.__name__ for i in self.context.implemented_interfaces()],
                'state': self.context.state,

                'cpu': self.context.cpu,
                'memory': self.context.memory,
                'os_release': self.context.os_release,
                'kernel': self.context.kernel,
                'network_usage': self.context.network_usage,
                'diskspace': self.context.diskspace,
                'swap_size': self.context.swap_size,
                'diskspace_rootpartition': self.context.diskspace_rootpartition,
                'diskspace_storagepartition': self.context.diskspace_storagepartition,
                'diskspace_vzpartition': self.context.diskspace_vzpartition,
                'diskspace_backuppartition': self.context.diskspace_backuppartition,
                'startup_timestamp': self.context.startup_timestamp,
                'bridge_interfaces': self._dummy_network_data()['bridge_interfaces'],
                }

        # XXX: generate random VM data:
        import random

        ret['vms'] = []

        vms = self.context['vms']
        if vms:
            for vm in vms.listcontent():
                ret['vms'].append(IHttpRestView(vm).render(request))

        return ret

    def _dummy_network_data(self):
        return {
            'bridge_interfaces': [{
                'id': 'vmbr1',
                'ipv4_address': '192.168.1.40',
                'ipv6_address': 'fe80::64ac:39ff:fe4a:e596/64',
                'subnet_mask': '255.255.255.0',
                'bcast': '192.168.1.255',
                'hw_address': '00:00:00:00:00:00',
                'metric': 1,
                'stp': False,
                'rx': '102.5MiB',
                'tx': '64.0MiB',
                'members': ['eth0', 'vnet0', 'vnet1', 'vnet5', 'vnet6',],
            }, {
                'id': 'vmbr2',
                'ipv4_address': '192.168.2.40',
                'ipv6_address': 'fe80::539b:28dd:db3b:c407/64',
                'subnet_mask': '255.255.255.0',
                'bcast': '192.168.2.255',
                'hw_address': '00:00:00:00:00:00',
                'metric': 1,
                'stp': False,
                'rx': '92.1MiB',
                'tx': '89.9MiB',
                'members': ['eth1', 'vnet1', 'vnet2', 'vnet3', 'vnet4',],
            }],
            'ip-routes': [{
                'dest': '192.168.1.125',
                'gateway': '0.0.0.0',
                'genmask': '255.255.255.255',
                'flags': 'UH',
                'metric': 0,
                'interface': 'venet0',
            }, {
                'dest': '192.168.2.125',
                'gateway': '0.0.0.0',
                'genmask': '255.255.255.255',
                'flags': 'UH',
                'metric': 0,
                'interface': 'venet1',
            }, {
                'dest': '192.168.3.125',
                'gateway': '0.0.0.0',
                'genmask': '255.255.255.255',
                'flags': 'UH',
                'metric': 0,
                'interface': 'venet2',
            }],
        }


class TemplatesView(HttpRestView):
    context(Templates)

    def render(self, request):
        return [{'name': name} for name in self.context.listnames()]



#~ # TODO: Move to a future config file/module.
#~ DEBUG = True


#~ class ComputeListResource(resource.Resource):

#~     def __init__(self, avatar=None):
#~         ## Twisted Resource is a not a new style class, so emulating a super-call
#~         resource.Resource.__init__(self)

#~         # TODO: This should be handled generically.
#~         self.avatar = avatar

#~     def getChild(self, path, request):
#~         # TODO: This should be handled generically.
#~         if not path: return self  # For trailing slahses.

#~         # TODO: This should be handled generically.
#~         return ComputeItemResource(path, avatar=self.avatar)

#~     def render_POST(self, request):
#~         # TODO: This should be handled generically.
#~         data = dict((k, request.args.get(k, [None])[0])
#~                     for k in ['name', 'hostname', 'ip', 'category'])
#~         deferred = ComputeBO().create_compute(data)

#~         @deferred
#~         def on_success((success, ret)):
#~             if success:
#~                 request.setResponseCode(201, 'Created')
#~                 request.setHeader('Location', ret)
#~             else:
#~                 request.setResponseCode(400, 'Bad Request')
#~             request.finish()

#~         @deferred
#~         def on_error(failure):
#~             failure = str(failure)
#~             log.err("Failed to create Compute", failure)
#~             request.setResponseCode(500, 'Server Error')
#~             if DEBUG: request.write(failure)
#~             request.finish()

#~         return NOT_DONE_YET


#~     def render_GET(self, request):
#~         deferred = ComputeBO().get_compute_all_basic()

#~         @deferred
#~         def on_success(info):
#~             request.write(json.dumps(info, indent=2) + '\n')
#~             request.finish()

#~         @deferred
#~         def on_error(failure):
#~             failure = str(failure)
#~             log.err("Failed to retrieve Compute list", failure)
#~             request.setResponseCode(500, 'Server Error')
#~             if DEBUG: request.write(failure)
#~             request.finish()

#~         return NOT_DONE_YET


#~ class ComputeItemResource(resource.Resource):

#~     def __init__(self, compute_id, avatar):
#~         resource.Resource.__init__(self)
#~         # TODO: This should be handled generically.
#~         self.avatar = avatar
#~         try:
#~             self.compute_id = int(compute_id)
#~         except ValueError:
#~             self.compute_id = None

#~     def getChild(self, path, request):
#~         # TODO: This should be handled generically.
#~         if not path: return self  # For trailing slahses.

#~         # TODO: This should be handled generically.
#~         self.compute_id = None
#~         return self

#~     def render_GET(self, request):
#~         # TODO: This should be handled generically.
#~         if self.compute_id is None:
#~             request.setResponseCode(404, 'Not Found')
#~             return ''

#~         deferred = ComputeBO().get_compute_one_basic(self.compute_id)

#~         @deferred
#~         def on_success(info):
#~             if not info:
#~                 request.setResponseCode(404, 'Not Found')
#~                 request.finish()
#~             else:
#~                 #~ request.setHeader('Content-Type', 'application/json')
#~                 #~ request.setHeader('Content-length', len(json.dumps(info) + '\n'))
#~                 request.write(json.dumps(info, indent=2) + '\n')
#~                 request.finish()

#~         @deferred
#~         def on_error(failure):
#~             failure = str(failure)
#~             log.err("Failed to retrieve Compute with ID %s" % self.compute_id, failure)
#~             request.setResponseCode(500, 'Server Error')
#~             if DEBUG: request.write(failure)
#~             request.finish()

#~         return NOT_DONE_YET
