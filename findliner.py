import os, glob
from sys import argv

font_size = 6
offset_top = int(argv[2]) if len(argv) > 2 else 0
offset_bottom = int(argv[3]) if len(argv) > 3 else 0
margin_left = int(argv[4]) if len(argv) > 4 else 35

from pathlib import Path

filename = Path(argv[1]).stem
file_extension = Path(argv[1]).suffix

if file_extension != '.pdf':
    print('Cannot open PDF. This file type ({}) is not supported.'.format(file_extension))
    quit()

from PyPDF2 import PdfReader

# Read your existing PDF
existing_pdf = PdfReader(open("{}.pdf".format(filename), "rb"))

number_of_pages = len(existing_pdf.pages)
lines = []

import tempfile

with tempfile.TemporaryDirectory() as tempdirname:

    # print(tempdirname)
    tempfilename = str(Path(tempdirname)/filename)
    png_filename = tempfilename+"-0" if number_of_pages == 1 else tempfilename # when pdf consists of a single page, imagemagick does not append a counter to the png file

    cmd = '''convert {}.pdf -strip png:{}
    for f in {}-*; do
        convert $f -flatten -resize 1X1000! -black-threshold 99% -white-threshold 10% -negate -morphology Erode Diamond -morphology Thinning:-1 Skeleton -black-threshold 50% txt:-| sed -e '1d' -e '/#000000/d' -e 's/^[^,]*,//' -e 's/[(]//g' -e 's/:.*//' -e 's/,/ /g' > $f.txt;
    done'''.format(filename, png_filename, tempfilename)

    os.system(cmd)

    for i in range(number_of_pages):
        with open('{}-{}.txt'.format(tempfilename, i)) as file:
            ys = [int(line) for line in file.readlines()]
            lines.append(ys[offset_top:len(ys)-offset_bottom])

from PyPDF2 import PdfWriter
import io
from reportlab.pdfgen import canvas
from reportlab.lib import colors

# Create a new PDF with Reportlab
packet = io.BytesIO()
can = canvas.Canvas(packet)

for i in range(number_of_pages):
    page = existing_pdf.pages[i]
    width = page.mediabox[2]
    height = page.mediabox[3]
    can.setPageSize((width, height))
    can.setFillColor(colors.red)
    can.setFont('Courier', font_size)
    line = lines[i]
    for j in range(len(line)):
        can.drawString(margin_left, int(height - height * line[j] / 1000) - font_size / 3, '{}.{}'.format(i+1, j+1))
    can.showPage()

can.save()

# Move to the beginning of the StringIO buffer
packet.seek(0)
new_pdf = PdfReader(packet)
output = PdfWriter()

# Add the "watermark" (which is the new pdf) on the existing page
for i in range(number_of_pages):
    page = existing_pdf.pages[i]
    page.merge_page(new_pdf.pages[i])
    output.add_page(page)

# Finally, write "output" to a real file
outputStream = open('{}-with-line-numbers-old.pdf'.format(filename), 'wb')
output.write(outputStream)
outputStream.close()