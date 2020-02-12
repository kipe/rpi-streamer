import os
from rpi_streamer.rpi_streamer import StreamingHandler, StreamingServer


class SubclassedStreamingHandler(StreamingHandler):
    INDEX_TEMPLATE = 'subclass.html'

    @property
    def template_paths(self):
        return [
            os.path.join(os.path.dirname(os.path.realpath(__file__)), 'templates')
        ] + super().template_paths


if __name__ == '__main__':
    try:
        server = StreamingServer(handler=SubclassedStreamingHandler)
        print('Starting camera server')
        server.serve_forever()
    except Exception as e:
        print(str(e))
    print('Stopping camera server')
