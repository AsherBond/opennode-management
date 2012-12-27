import json
import os
import time

from grokcore.component import context
from hashlib import sha1
from twisted.internet import defer
from twisted.web.server import NOT_DONE_YET
from zope.component import queryAdapter, handle
from zope.security.interfaces import Unauthorized
from zope.security.proxy import removeSecurityProxy

from opennode.oms.endpoint.httprest.base import HttpRestView, IHttpRestView
from opennode.oms.endpoint.httprest.root import BadRequest
from opennode.oms.endpoint.ssh.cmd.security import effective_perms
from opennode.oms.model.form import ApplyRawData, ModelDeletedEvent
from opennode.oms.model.location import ILocation
from opennode.oms.model.model.base import IContainer
from opennode.oms.model.model.bin import ICommand
from opennode.oms.model.model.byname import ByNameContainer
from opennode.oms.model.model.filtrable import IFiltrable
from opennode.oms.model.model.search import SearchContainer, SearchResult
from opennode.oms.model.model.stream import IStream, StreamSubscriber
from opennode.oms.model.model.symlink import follow_symlinks
from opennode.oms.model.schema import model_to_dict
from opennode.oms.model.traversal import traverse_path
from opennode.oms.security.checker import get_interaction
from opennode.oms.zodb import db


class DefaultView(HttpRestView):
    context(object)

    def render_GET(self, request):
        data = model_to_dict(self.context)

        data['id'] = self.context.__name__
        data['__type__'] = type(removeSecurityProxy(self.context)).__name__
        data['url'] = ILocation(self.context).get_url()

        interaction = get_interaction(self.context)
        data['permissions'] = effective_perms(interaction, self.context) if interaction else []

        # XXX: Temporary hack--simplejson can't serialize sets
        if 'tags' in data:
            data['tags'] = list(data['tags'])

        return data

    def render_PUT(self, request):
        data = json.load(request.content)
        if 'id' in data:
            del data['id']

        data = self.put_filter_attributes(request, data)

        form = ApplyRawData(data, obj=self.context)
        if not form.errors:
            form.apply()
            return [IHttpRestView(self.context).render_recursive(request, depth=0)]
        else:
            request.setResponseCode(BadRequest.status_code)
            return form.error_dict()

    def put_filter_attributes(self, request, data):
        """Offer the possibility to subclasses to massage the received json before default behavior."""
        return data

    def render_DELETE(self, request):
        force = request.args.get('force', ['false'])[0] == 'true'

        parent = self.context.__parent__
        del parent[self.context.__name__]

        try:
            handle(self.context, ModelDeletedEvent(parent))
        except Exception as e:
            if not force:
                raise e
            return {'status': 'failure'}

        return {'status': 'success'}


class ContainerView(DefaultView):
    context(IContainer)

    def render_GET(self, request):
        depth = request.args.get('depth', ['0'])[0]
        try:
            depth = int(depth)
        except ValueError:
            depth = 0
        return self.render_recursive(request, depth, top_level=True)

    def render_recursive(self, request, depth, top_level=False):
        container_properties = super(ContainerView, self).render_GET(request)

        if depth < 1:
            return self.filter_attributes(request, container_properties)

        exclude = [i.strip() for i in request.args.get('exclude', [''])[0].split(',')]
        items = [follow_symlinks(i) for i in self.context.listcontent() if i.__name__ not in exclude]

        def secure_render_recursive(item):
            try:
                return IHttpRestView(item).render_recursive(request, depth - 1)
            except Unauthorized:
                permissions = effective_perms(get_interaction(item), item)
                return dict(access='denied', permissions=permissions,
                            __type__=type(removeSecurityProxy(item)).__name__)

        # XXX: temporary code until ONC uses /search also for filtering computes
        q = None
        limit = None
        offset = 0

        if top_level:
            q = request.args.get('q', [''])[0]
            q = q.decode('utf-8')

            limit = int(request.args.get('limit', [0])[0])
            offset = int(request.args.get('offset', [0])[0])

        if q:
            items = [item for item in items if IFiltrable(item).match(q)]

        if limit or offset:
            items = items[offset:limit]

        children = [secure_render_recursive(item)
                    for item in items
                    if queryAdapter(item, IHttpRestView) and not self.blacklisted(item)]

        # backward compatibility:
        # top level results for pure containers are plain lists
        if top_level and (not container_properties or len(container_properties.keys()) == 1):
            return children

        #if not top_level or depth > 1:
        #if depth > 1:
        if not top_level or depth > 0:
            container_properties['children'] = children
        return self.filter_attributes(request, container_properties)

    def blacklisted(self, item):
        return isinstance(item, ByNameContainer)


class SearchView(ContainerView):
    context(SearchContainer)

    def render_GET(self, request):
        q = request.args.get('q', [''])[0]
        q = q.decode('utf-8')

        if not q:
            return super(SearchView, self).render_GET(request)

        search = db.get_root()['oms_root']['search']
        res = SearchResult(search, q)

        return IHttpRestView(res).render_GET(request)


class StreamView(HttpRestView):
    context(StreamSubscriber)

    cached_subscriptions = dict()

    def rw_transaction(self, request):
        return False

    def render(self, request):
        timestamp = int(time.time() * 1000)
        oms_root = db.get_root()['oms_root']

        limit = int(request.args.get('limit', ['100'])[0])
        after = int(request.args.get('after', ['0'])[0])

        subscription_hash = request.args.get('subscription_hash', [''])[0]
        if subscription_hash:
            if subscription_hash in self.cached_subscriptions:
                data = self.cached_subscriptions[subscription_hash]
            else:
                raise BadRequest("Unknown subscription hash")
        else:
            if not request.content.getvalue() and not request.args.get('subscription_hash', [''])[0]:
                return {}
            data = json.load(request.content)
            subscription_hash = sha1(request.content.getvalue()).hexdigest()
            self.cached_subscriptions[subscription_hash] = data
            request.responseHeaders.addRawHeader('X-OMS-Subscription-Hash', subscription_hash)

        def val(r):
            objs, unresolved_path = traverse_path(oms_root, r)
            if unresolved_path:
                return [(timestamp, dict(event='delete', name=os.path.basename(r), url=r))]
            return IStream(objs[-1]).events(after, limit=limit)

        # ONC wants it in ascending time order
        # while internally we prefer to keep it newest first to
        # speed up filtering.
        # Reversed is not json serializable so we have to reify to list.
        res = [list(reversed(val(resource))) for resource in data]
        res = [(i, v) for i, v in enumerate(res) if v]
        return [timestamp, dict(res)]


class CommandView(DefaultView):
    context(ICommand)

    def render_PUT(self, request):
        @defer.inlineCallbacks
        def call_action():
            from opennode.oms.endpoint.ssh.detached import DetachedProtocol

            yield self.context.cmd(DetachedProtocol()).execute(object())
            request.write(json.dumps({"status": "ok"}))
            request.finish()

        call_action()
        return NOT_DONE_YET
