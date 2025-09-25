from json import dumps
from logging import INFO
from multiprocessing import Process
from tempfile import NamedTemporaryFile
from socket import socket, AF_INET, SOCK_DGRAM
from capstone.utils.logs import setup_logging
from capstone.proxmox.answer_file.answer_file import gen_ans_file_with
from flask import Flask, request, make_response, jsonify, send_file

cached_answer_files = {}

app = Flask(
    "capstone.proxmox.auto_installer.answer_server"
    if __name__ == "__main__"
    else __name__
)


def _get_ip() -> str:
    s = socket(AF_INET, SOCK_DGRAM)
    try:
        s.connect(("10.254.254.254", 1))
        ip = s.getsockname()
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip[0] if isinstance(ip, tuple) else ip  # type: ignore


@app.route("/api/answer_file", methods=["POST"])
def answer_file():
    data = request.json
    if not data:
        return make_response(jsonify({"error": "Invalid JSON data"}), 400)
    key = data["network_interfaces"][0].get("mac", "unknown")
    if key in cached_answer_files:
        print(f"Serving cached answer file for {key}")
        # Write the answer file content to a temporary file
        temp = NamedTemporaryFile(delete=False, mode="w+", suffix=".toml")
        temp.write(cached_answer_files[key])  # type: ignore
        app.logger.info(f"Answer file content:\n{cached_answer_files[key]}")
        temp.flush()
        temp.seek(0)
        response = send_file(
            temp.name,
            as_attachment=True,
            download_name="answer_file.toml",
            mimetype="text/plain",
        )
        return response
    else:
        app.logger.error(f"No cached answer file for {key}")
        # use the data from the request to find the network interface and disk
        return make_response(
            jsonify({"error": "No answer file found for this client"}), 404
        )


@app.route("/api/device_discovery", methods=["POST"])
def device_discovery():
    # print out the req body
    data = request.json
    if not data:
        return make_response(jsonify({"error": "Invalid JSON data"}), 400)

    key = data["mgmt_mac"]
    disk = data["disk"]

    if key not in cached_answer_files:
        cached_answer_files[key] = gen_ans_file_with(key, disk)
        app.logger.info(f"Generated new answer file for {key}")
    app.logger.info("Device Discovery Data Received:")
    app.logger.info(dumps(data, indent=4))
    return make_response(jsonify({"message": "Device discovery data received"}), 200)


def _start_server_new_process():
    p = Process(target=start_answer_server)
    p.start()
    return p


def start_answer_server():
    app.run(host=_get_ip(), port=5000, debug=True)


def main():
    server_process = None
    app.logger.setLevel("INFO")
    try:
        server_process = _start_server_new_process()
        server_process.join()
    except KeyboardInterrupt:
        app.logger.info("Shutting down the server.")
    except Exception as e:
        app.logger.error(f"An error occurred: {e}")
    finally:
        if server_process:
            server_process.terminate()
            server_process.join()
        app.logger.info("Server has been shut down.")


if __name__ == "__main__":
    setup_logging(level=INFO)
    main()
