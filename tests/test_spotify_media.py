from PIL import Image

from spotify_media import requested_spotify_query, _top_result_button


def test_spotify_request_parsing():
    assert requested_spotify_query("okay can you please open spotify and play a naath") == "naath"
    assert requested_spotify_query("play Tajdar-e-Haram on Spotify") == "Tajdar-e-Haram"
    assert requested_spotify_query("open Spotify") is None


def test_top_result_button_requires_green_circle():
    image = Image.new("RGB", (1000, 600), (10, 10, 10))
    assert _top_result_button(image, (0, 0, 1000, 600)) is None
    for y in range(120, 181):
        for x in range(650, 711):
            if (x - 680) ** 2 + (y - 150) ** 2 < 30 ** 2:
                image.putpixel((x, y), (30, 215, 96))
    assert _top_result_button(image, (0, 0, 1000, 600)) == (680, 150)
