import copy
import json

from aiohttp import web

from core.crawler import crawl
from models.response import FailedResponse

dashboard_data_template = {
    'code': 20000,
    'data': {
        'items': [],
        'total': 0
    }
}


async def dashboard(request):
    dashboard_router = {
        '/prod-api/patterns': patterns,
        '/prod-api/pattern': pattern,
        '/prod-api/proxies': proxies,
        '/prod-api/user/login': login,
        '/prod-api/user/logout': logout,
        '/prod-api/user/info': user_info,
        '/prod-api/status': status,
        '/prod-api/index': index,
        '/prod-api/config': config,
        '/prod-api/recent_failed_request': recent_failed_request,
        '/prod-api/debug': debug,
    }
    path = request.path
    if path in dashboard_router:
        return await dashboard_router[path](request)
    return web.Response(status=200, text="hello world")


async def debug(request):
    info = await request.json()
    url = info['url']
    method = info['method']
    if isinstance(info['headers'], str):
        headers = json.loads(info['headers'])
    else:
        headers = info['headers']
    data = info['data']
    proxy = info['proxy']
    response = await crawl(method, url, [proxy], headers=headers, data=data)
    if isinstance(response, FailedResponse):
        html = response.traceback.replace('\n', '<br>')
    else:
        html = await response.text()
    return web.json_response({'code': 20000, 'html': html})


async def patterns(request):
    r = copy.deepcopy(dashboard_data_template)
    items = await request.app['pam'].patterns(format_type='dict')
    r['data']['items'] = items
    r['data']['total'] = len(items)
    return web.json_response(data=r)


async def proxies(request):
    if request.method == 'GET':
        r = copy.deepcopy(dashboard_data_template)
        pattern_str = request.query.get('pattern', 'public_proxies')
        items = await request.app['pom'].proxies(pattern_str=pattern_str, format_type='dict')
        r['data']['items'] = items
        r['data']['total'] = len(items)
        return web.json_response(data=r)
    elif request.method == 'DELETE':
        pattern_str = request.query.get('pattern', 'public_proxies')
        await request.app['pom'].clean_proxies(pattern_str=pattern_str)
        return web.json_response(data={'code': 20000, 'message': 'success'})


async def login(request):
    info = await request.json()
    username, password = info['username'], info['password']
    # accept any password
    if username == 'admin':
        return web.json_response(data={'code': 20000, 'data': {'token': 'admin'}})
    else:
        return web.json_response(data={'code': 60204, 'message': 'Account and password are incorrect.'})


async def logout(request):
    return web.json_response(data={'code': 20000, 'message': 'success'})


async def status(request):
    r = copy.deepcopy(dashboard_data_template)
    x, items = request.app['pam'].status()
    r['data']['items'] = items
    r['data']['x'] = x
    r['data']['total'] = len(r['data']['items'])
    return web.json_response(data=r)


async def index(request):
    data = {
        'proxy_count': await request.app['pom'].proxy_count('public_proxies'),
        'pattern_count': await request.app['pam'].pattern_count(),
        'success_requests': request.app['sv'].success_count,
        'total_requests': request.app['sv'].total_count
    }
    return web.json_response(data={'code': 20000, 'data': data})


async def user_info(request):
    return web.json_response(data={'code': 20000, 'data': request.app['config'].admin_token})


async def pattern(request):
    d = await request.json()
    if request.method == 'POST':
        await request.app['pam'].add(d['pattern'], d['rule'], d['value'])
    elif request.method == 'DELETE':
        await request.app['pam'].delete(d['pattern'])
    return web.json_response(data={'code': 20000, 'message': 'success'})


async def recent_failed_request(request):
    d = await request.json()
    pattern_str = d['pattern']
    _pattern = request.app['pam'].get_pattern(pattern_str)
    items = await _pattern.recent_failed_request(request.app['redis'])
    r = copy.deepcopy(dashboard_data_template)
    r['data']['items'] = items
    r['data']['total'] = len(items)
    return web.json_response(data=r)


async def config(request):
    fields = ['mode', 'pool_size', 'concurrent', 'timeout']
    if request.method == 'GET':
        data = dict()
        for k in fields:
            if hasattr(request.app['config'], k):
                data[k] = getattr(request.app['config'], k)
        return web.json_response(data={'code': 20000, 'data': data})
    elif request.method == "POST":
        data = await request.json()
        for k in data:
            if k in fields:
                setattr(request.app['config'], k, data[k])
        return web.json_response(data={'code': 20000, 'message': 'success'})
