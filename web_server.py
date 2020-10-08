# -*- coding: utf-8 -*-
import os
import sys
import json
import cherrypy
import requests as rq
PATH = os.path.abspath(os.path.dirname(__file__)) + "/html"



""" Basic auth """
from cherrypy.lib import auth_basic
USERS = {'hoge': 'huga'}
def validate_password(realm, username, password):
    if username in USERS and USERS[username] == password:
       return True
    return False

""" Allow access white list"""
white_list = set(["0.0.0.", "127.0.0.1"])  # For Debug
@cherrypy.tools.register('before_request_body')
def logit():
    ip = ""
    ua = cherrypy.request.headers.get("User-Agent")
    if "X-Remote-Addr" in cherrypy.request.headers:
        ip = cherrypy.request.headers["X-Remote-Addr"]
    elif "X-Real-Ip" in cherrypy.request.headers:
        ip = cherrypy.request.headers["X-Real-Ip"]
    elif "X-Forwarded-For" in cherrypy.request.headers:
        ip = cherrypy.request.headers["X-Forwarded-For"]
    else:
        ip = cherrypy.request.headers["Remote-Addr"]
    check = False
    for addr in white_list:
        if ip.startswith(addr):
            check = True
            break
    check = True        # 全員通す
    if check == False:
        raise cherrypy.HTTPError(401)




class Translate(object):
    exposed = True

    @cherrypy.tools.accept(media='application/json')
    def POST(self, text="", source_lang="", target_lang=""):
        api_key = ""    # NOTE: plese specify your api key for DeepL API.
        if len(api_key) == 0:
            return(json.dumps({"status":"success", "translation":""}))

        param_d = {"auth_key": api_key, 
                   "text":text, 
                   "source_lang":source_lang, 
                   "target_lang":target_lang}
        try:
            request_d = rq.post("https://api.deepl.com/v2/translate", data=param_d)
            translated_text_d = request_d.json()["translations"][0]["text"]
        except:
            translated_text_d = ""
        return(json.dumps({"status":"success", "translation":translated_text_d}))


class Root(object): 
    @cherrypy.expose
    @cherrypy.tools.logit()
    def default(self):
        pass

conf = {
    '/': {
        'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
        'request.show_tracebacks': False,
        'tools.trailing_slash.missing': False,
#        'tools.auth_basic.on': True,
#        'tools.auth_basic.realm': 'localhost',
#        'tools.auth_basic.checkpassword': validate_password,
#        'tools.auth_basic.accept_charset': 'UTF-8',
    }
}

conf_static = {
    '/': {
        'request.show_tracebacks': False,
        'tools.staticdir.on': True,
        'tools.staticdir.dir': PATH,
        'tools.staticdir.index': 'index.html', 
#        'tools.auth_basic.on': True,
#        'tools.auth_basic.realm': 'localhost',
#        'tools.auth_basic.checkpassword': validate_password,
#        'tools.auth_basic.accept_charset': 'UTF-8',
    }
}

cherrypy.__version__ = ''
cherrypy._cperror._HTTPErrorTemplate = cherrypy._cperror._HTTPErrorTemplate.replace('Powered by <a href="http://www.cherrypy.org">CherryPy %(version)s</a>\n','%(version)s')

cherrypy.config.update({'server.socket_host': '0.0.0.0',
                        'server.socket_port': 8000,
                        'log.screen': True})


cherrypy.tree.mount(Root(),             '/web', conf_static)
cherrypy.tree.mount(Translate(),      '/api/translate/', conf)


cherrypy.engine.start()
cherrypy.engine.block()
