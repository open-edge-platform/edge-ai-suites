import socketio
import eventlet

sio = socketio.Server(async_mode='eventlet', ping_timeout=3600)
app = socketio.Middleware(sio)

@sio.event
def connect(sid, environ):
    print('connect', sid)

@sio.event
def cmd(sid, msg):
    sio.emit(msg['name'], msg['text'])

@sio.event
def disconnect(sid):
    print('disconnect', sid)

def socket_server_start():
    eventlet.wsgi.server(eventlet.listen(('127.0.0.1', 3000)), app)

if __name__ == '__main__':
    socket_server_start()
