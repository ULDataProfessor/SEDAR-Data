import os
import subprocess
import time
from tempfile import NamedTemporaryFile
from typing import List
from urllib.parse import urljoin

import requests
from lxml import html

CHALLENGE = "http://www.sedar.com/GetFile.do?lang=EN&docClass=13&issuerNo=00020297&fileName=/foo"
RESPONSE = "http://www.sedar.com/CheckCode.do"


def bin_name(*paths: str) -> str:
    """
    Checks the provided paths and returns the path if it is a file.

    :param paths: A list of paths to check
    :return: The first valid path that is a file
    :raise ValueError: When no valid file path is found
    """
    for path in paths:
        if os.path.isfile(path):
            return path
    raise ValueError(f"No binary available: {paths}")


def temp_name() -> str:
    """
    Creates a temporary file and returns its name.

    :return: The name of the temporary file
    """
    with NamedTemporaryFile() as tmp:
        return tmp.name


def improve_image(image: str) -> str:
    """
    Enhances an image for better OCR recognition.

    :param image: Path of the image to be enhanced
    :return: Path of the enhanced image
    """
    null = os.open(os.devnull, os.O_APPEND)
    tmp = temp_name() + ".jpg"
    args = [bin_name("/usr/local/bin/gm", "/usr/bin/gm"), "convert"]
    args.extend(
        [
            "-contrast",
            "-contrast",
            "-contrast",
            "-contrast",
            "-contrast",
            "-contrast",
            "-modulate",
            "120",
            "-sharpen",
            "0x1.0",
            "-antialias",
            "-despeckle",
            "-despeckle",
            "-despeckle",
            "-despeckle",
            "-despeckle",
            "-despeckle",
            image,
            tmp,
        ]
    )
    subprocess.run(args, stdout=null, stderr=null)
    os.close(null)
    return tmp


def run_ocr(image: str) -> str:
    """
    Performs OCR on the image and returns the result.

    :param image: Path of the image to perform OCR on
    :return: OCR result
    """
    null = os.open(os.devnull, os.O_APPEND)
    tmp = temp_name()
    print(f"OCRing {image}")
    bin_ = bin_name("/usr/local/bin/tesseract", "/usr/bin/tesseract")
    args = [bin_, image, tmp, "-l", "eng", "-psm", "8"]
    subprocess.run(args, stdout=null, stderr=null)
    os.close(null)
    with open(f"{tmp}.txt", "r") as fh:
        return fh.read().strip()


def break_captcha(srcs: List[str]) -> str:
    """
    Breaks the captcha by running OCR on each source image.

    :param srcs: List of source image URLs
    :return: Concatenated OCR result
    """
    code = []
    for src in srcs:
        res = requests.get(src)
        tmp = temp_name() + ".jpg"
        with open(tmp, "wb") as fh:
            fh.write(res.content)
        clean = improve_image(tmp)
        char = run_ocr(clean)
        code.append(char)
    return "".join(code)


def make_cracked_session() -> requests.Session:
    """
    Attempts to break the captcha until successful.

    :return: Session after successfully breaking the captcha
    """
    print("Trying to break captcha....")
    while True:
        try:
            sess = requests.Session()
            res = sess.get(CHALLENGE)
            doc = html.fromstring(res.content)
            srcs = [urljoin(CHALLENGE, i.get("src")) for i in doc.findall(".//img")]
            code = break_captcha(srcs)
            if len(code) != len(srcs):
                print(f"Wrong length guess {code}")
                continue
            resp_url = urljoin(CHALLENGE, doc.find(".//form").get("action"))
            print(f"Guessed captcha {code}")
            res = sess.post(resp_url, data={"code": code})
            if b"did not match" in res.content:
                print("Did it blend? No.")
                continue
            print("Did it blend? Yes.")
            return sess
        except Exception as e:
            print(e)
            time.sleep(15)
