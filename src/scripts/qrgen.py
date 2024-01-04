# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2023 Digital CUBE <https://digitalcube.rs>

from PIL import Image, ImageDraw, ImageFont  # Corrected import statement
import PIL

import qrcode

l = {"LANE1":"5a25539b-b8f2-4b9d-ad7e-d607bb248835",
                "LANE2":"e4041668-8199-48c5-bb00-0b4e7042f479",
                "LANE3":"6aa3dbb8-9140-4f0c-8da2-e7c02d855d6b",
                "LANE4":"71619b8e-f9f1-4537-a33d-0f69f117af6b",
                "LANE5":"b22cce38-b33b-44a2-8f1d-8bc4ebe1e3d3",
                "LANE6":"f5a33c2a-2112-497f-a781-71a2a6dc471d",
                "LANE-DC":"b5b574fc-a854-4666-82c7-8b22877bf000"
                }
                
# Define the UUID

for luid in l:

    uid = l[luid]

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )

    qr.add_data(uid)
    qr.make(fit=True)

    img =  PIL.Image.new("1",(370,450),255)

    img_qr = qr.make_image(fill_color="black", back_color="white")

    img_draw = PIL.ImageDraw.Draw(img)
    
    font =  ImageFont.truetype("./font.ttf", 64)

    img.paste(img_qr, (0,0))
    
    img_draw.text((370/2-95,360), luid, fill='black', font=font, )
    
    
    img.save(f"uuid_{luid}.png")
