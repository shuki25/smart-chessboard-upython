"""
Universal Chess Interface (UCI) protocol implementation.

This module implements the UCI protocol for communicating with chess engines.
It is based on the UCI protocol specification version 2.0.

The UCI protocol is a text-based protocol. Commands are sent from the GUI to
the engine and the engine responds with information to the GUI by text
commands sent back. All text commands are using the ASCII character set. The
UCI engine should be able to receive and send commands as fast as possible
without any delay. The engine should not wait for a complete command before
it starts to process the command. The engine should also not wait for a
response from the GUI before it starts to process the next command.

The UCI protocol is designed to be as simple as possible. The GUI should be
able to send commands to the engine and receive information from the engine
without any knowledge about the internal workings of the engine. The engine
should be able to receive commands from the GUI and send information to the
GUI without any knowledge about the internal workings of the GUI.
"""

try:
    import uasyncio as asyncio
except ImportError:
    import asyncio


def parse_info(info: str) -> dict:
    """
    Parse the "info" command from the chess engine.
    """
    if not info.startswith("info"):
        raise ValueError("info must start with 'info'")

    info_dict = {}

    # Split the info string into a list of key-value pairs.
    info_list = info.split(" ")[1:]

    # Split the key-value pairs into a dictionary.

    i = 0
    size = len(info_list)

    while i < size:
        item = info_list[i]
        if item == "score":
            info_dict["score"] = info_list[i+1] + " " + info_list[i+2]
            i += 3
            continue
        elif item == "upperbound":
            i += 1
            continue
        elif item == "string":
            info_dict["string"] = " ".join(info_list[i+1:])
            break
        elif item != "pv":
            info_dict[item] = info_list[i+1]
            i += 2
        else:
            info_dict["pv"] = " ".join(info_list[i+1:])
            break

    return info_dict


class UCI:
    """
    UCI protocol implementation.

    This class implements the UCI protocol for communicating with chess engines.
    """
    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter
    connected: bool

    def __init__(self, host: str, port: int = 9999, level: int = 1):
        """
        :param host: The host name or IP address of the chess engine.
        :param port: The port number of the chess engine.
        :param level: The level of the chess engine.
        """

        if not isinstance(host, str):
            raise TypeError("host must be a string")

        if not host:
            raise ValueError("host must not be empty")

        self.host = host
        self.port = port
        self.level = level

    async def start(self):
        """
        Start the UCI protocol.
        """
        # Create a connection to the chess engine.
        self.reader, self.writer = await asyncio.open_connection(self.host, self.port)

        # Send the "uci" command to the chess engine.
        self.writer.write(b"uci\n")
        print("Sent: uci")

        # Read the response from the chess engine.
        while True:
            response = await self.reader.readline()
            clean_response = response.decode().strip()
            print("Received: %s" % clean_response)

            if clean_response == "uciok":
                self.connected = True
                break

        # Send the "setoption" command to the chess engine.
        self.writer.write(b"setoption name Skill Level value %d\n" % self.level)
        print("Sent: setoption name Skill Level value %d" % self.level)

        # Send the "isready" command to the chess engine.
        self.writer.write(b"isready\n")
        print("Sent: isready")

        # Read the response from the chess engine.
        while True:
            response = await self.reader.readline()
            clean_response = response.decode().strip()
            print("Received: %s" % clean_response)

            if clean_response == "readyok":
                break

        print("Engine is ready")

        # Send the "ucinewgame" command to the chess engine.
        self.writer.write(b"ucinewgame\n")
        print("Sent: ucinewgame")

        # Send the "position" command to the chess engine.
        self.writer.write(b"position startpos\n")
        print("Sent: position startpos")

    def stop(self):
        """
        Stop the UCI protocol.
        """
        self.writer.close()
        self.connected = False
        print("Connection closed")

    def go(self, fen: str, depth: int = 1, movetime: int = 1000):
        """
        Send the "go" command to the chess engine.
        """
        if not self.connected:
            raise RuntimeError("Engine is not connected")

        # Send the "position" command to the chess engine.
        self.writer.write(b"position fen %s\n" % fen.encode())
        print("Sent: position fen %s" % fen)

        # Send the "go" command to the chess engine.
        self.writer.write(b"go depth %d movetime %d\n" % (depth, movetime))

    async def engine_response(self, match_string: list = None, timeout: int = 0.2) \
            -> str or None:
        """
        Read the response from the chess engine.
        """
        # Read the response from the chess engine.
        if len(match_string):
            while True:
                try:
                    response = await asyncio.wait_for(self.reader.readline(), timeout=timeout)
                    clean_response = response.decode().strip()
                    print("Received: %s" % clean_response)
                except asyncio.TimeoutError:
                    clean_response = None
                if clean_response:
                    for word in match_string:
                        if clean_response.startswith(word):
                            return clean_response
        else:
            try:
                response = await asyncio.wait_for(self.reader.readline(), timeout=0.2)
                clean_response = response.decode().strip()
            except asyncio.TimeoutError:
                clean_response = None

        return clean_response

