#!/usr/bin/env python3
# the device used is a raspberry pico connected to a 800x480 display
# https://shop.sb-components.co.uk/products/enkpi
# the display itself can't run much code. So we render the image on the server
# and then we can serve it up in a bitstream that can be streamed directly to
# the screen. Keeping the interface on the device slow
import io
import logging
import os
import threading

from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qsl, urlparse, parse_qs
from functools import cached_property

from PIL import Image

logger = logging.getLogger(__name__)
dir_path = os.path.dirname(os.path.realpath(__file__))

class WebRequestHandler(BaseHTTPRequestHandler):
    '''A webserver for our the enkpi. It renders an image as a png
    or as a stream of bytes for direct use with an e-ink display'''

    file = os.path.join(dir_path, './static/images/current_image.png')

    @cached_property
    def url(self):
        return urlparse(self.path)

    @cached_property
    def query(self):
        return dict(parse_qs(self.url.query))

    def response(self):
        with io.BytesIO() as image_io:
            with Image.open(self.file) as image:
                image.save(image_io, format='PNG')
                png_img = image_io.getvalue()

                # Set the appropriate HTTP headers
                self.send_response(200)
                self.send_header('Content-Type', 'image/png')
                self.send_header('Content-Length', len(png_img))
                self.end_headers()
                #write the image
                self.wfile.write(png_img)

    def response_bytearray(self, start=0, end=-1):
        with io.BytesIO() as ppm_buf:
            with Image.open(self.file) as img:
                # convert to 1bit ppm
                image = img.convert('1')
                image.save(ppm_buf, format='PPM')

                # uncomment for debugging
                # logger.info("saving to /tmp/weather-bw.ppm")
                # image.save("/tmp/weather-bw.ppm")

                # skip over the first 2 lines, read in the bytes on the 3rd line
                count = 0
                image_data = []
                for byte in ppm_buf.getvalue():
                    if count >= 2:
                        # Xor with 0xff to invert the image
                        image_data.append(byte ^ 0xff)
                    if byte == ord('\n'):
                        count += 1

                # subset the data if they have asked for it
                image_data = image_data[start:end]

                self.send_response(200)
                self.send_header('Content-Type', 'application/octet-stream')
                self.send_header('Content-Length', len(image_data))
                self.end_headers()
                #write the image
                self.wfile.write(bytes(image_data))

    def do_GET(self):
        if "byte" in self.query:
            logger.info("rendering ppm")
            start = int(self.query.get("start", [0])[0])
            end  = int(self.query.get("end", [-1])[0])
            self.response_bytearray(start=start, end=end)
        else:
            logger.info("rendering png")
            self.response()


    def do_POST(self):
        self.do_GET()

class EnkServer:

    def __init__(self):
        self.thread = None
        self.running = False

    def start(self):
        """Starts the enk server background thread"""
        if not self.thread or not self.thread.is_alive():
            logger.info("starting EnkServer task")
            self.thread = threading.Thread(target=self._run, daemon=True)
            self.running = True
            self.thread.start()


    def stop(self):
        self.running = False
        if self.thread:
            self.server.shutdown()
            self.thread.join()

    def _run(self):
        port = 9187
        logger.info("starting enkpi server on port %d", port)
        self.server = HTTPServer(("0.0.0.0", port), WebRequestHandler)
        self.server.serve_forever()



if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    es = EnkServer()
    es._run()

