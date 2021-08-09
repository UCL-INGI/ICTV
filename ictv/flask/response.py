import flask

def created():
    flask.make_response('201 Created', 201)

def nocontent():
    flask.abort(204, '204 No Content')

def seeother(url):
    flask.abort(flask.redirect(url, code=303))

def badrequest(message=None):
    flask.abort(400, message)

def forbidden(message=None):
    flask.abort(403, message)

def notfound(message=None):
    flask.abort(404, message)

def nomethod():
    flask.abort(405,'405 Method Not Allowed')

def internalerror(message=None):
    flask.abort(500,message)
