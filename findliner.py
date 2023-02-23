from sys import argv
import pathlib, tempfile, subprocess, io
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas as reportlab_canvas

font_size = 6
baseline_shift = 2
offset_top = int(argv[2]) if len(argv) > 2 else 0
offset_bottom = int(argv[3]) if len(argv) > 3 else 0
margin_left = int(argv[4]) if len(argv) > 4 else 35

file = pathlib.Path(argv[1])
filename = pathlib.Path(argv[1]).stem
file_extension = pathlib.Path(argv[1]).suffix.lower()

if file_extension != '.pdf':
    print('Can open only PDF. This file type ({}) is not supported.'.format(file_extension))
    quit()

# Read your existing PDF
existing_pdf = PdfReader(file)

number_of_pages = len(existing_pdf.pages)
lines_per_page = []
png_heights = []

with tempfile.TemporaryDirectory() as temp_dir:
    png_fn = str(pathlib.Path(temp_dir)/'pngs')
    pdf_fn = str(pathlib.Path(temp_dir)/'pdf')

    # Repair potentially corrupted PDF
    # https://superuser.com/questions/278562/how-can-i-fix-repair-a-corrupted-pdf-file/282056#282056
    subprocess.run(['gs', '-o', pdf_fn, '-sDEVICE=pdfwrite', '-dPDFSETTINGS=/prepress', file])
    
    # Reread your existing PDF
    existing_pdf = PdfReader(pdf_fn)

    # When pdf consists of a single page, imagemagick does not append a counter to the png file
    png_fn_alt = png_fn + '-0' if number_of_pages == 1 else png_fn
    subprocess.run(['convert', pdf_fn, '-strip', 'png:{}'.format(png_fn_alt)])

    for idx in range(number_of_pages):
        print('Processing {}/{}...'.format(idx+1, number_of_pages))
        dimension = subprocess.run(['identify', '-ping', '-format', "'%w %h'", '{}-{}'.format(png_fn, idx)], capture_output=True, encoding='utf8').stdout[1:-1]
        height = int(dimension.split()[1])
        png_heights.append(height)
        blob = subprocess.run(['convert', '{}-{}'.format(png_fn, idx), '-flatten', '-resize', '1X{}!'.format(height), '-black-threshold', '99%', '-white-threshold', '10%', '-negate', '-morphology', 'Erode', 'Diamond', '-morphology', 'Thinning:-1', 'Skeleton', '-black-threshold', '50%', 'txt:-'], capture_output=True, encoding='utf8').stdout
        lines = []
        for line in blob.splitlines()[1:]:
            if not('#0000000' in line):
                lines.append(int(line.split(':')[0].split(',')[1]))
        lines_per_page.append(lines[offset_top:len(lines)-offset_bottom])

## Add text to existing PDF using Python
# https://stackoverflow.com/questions/1180115/add-text-to-existing-pdf-using-python

# Create a new PDF with Reportlab
packet = io.BytesIO()
canvas = reportlab_canvas.Canvas(packet)

for idx, lines in enumerate(lines_per_page):
    page = existing_pdf.pages[idx]
    width = page.mediabox[2]
    height = page.mediabox[3]
    canvas.setPageSize((width, height))
    canvas.setFont('Courier', font_size)
    for j, y in enumerate(lines):
        canvas.drawString(margin_left, int(height - y * height / png_heights[idx]) - baseline_shift, '{}.{}'.format(idx+1, j+1))
    canvas.showPage()

canvas.save()

# Move to the beginning of the StringIO buffer
packet.seek(0)

# Create a new PDF with Reportlab
new_pdf = PdfReader(packet)
output = PdfWriter()

# Add the line numbers (which is the new pdf) on the existing page
for idx in range(number_of_pages):
    page = existing_pdf.pages[idx]
    page.merge_page(new_pdf.pages[idx])
    output.add_page(page)

# Finally, write "output" to a real file
outputStream = open(file.parents[0]/'{}-with-line-numbers.pdf'.format(filename), 'wb')
output.write(outputStream)
outputStream.close()
