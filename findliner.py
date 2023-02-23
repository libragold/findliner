#!/usr/bin/env python3

from sys import argv
import pathlib, tempfile, subprocess, io
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas as reportlab_canvas
import os

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


def generate_png(pdf_fn, png_fn):
    # When pdf consists of a single page, imagemagick does not append a counter to the png file
    png_fn_alt = png_fn + '-0' if number_of_pages == 1 else png_fn
    cmd = ['convert', pdf_fn, '-strip', 'png:{}'.format(png_fn_alt)]
    # cmd = ['convert', pdf_fn, '-strip', 'png:{}'.format(png_fn_alt)]
    print(' '.join(cmd))
    subprocess.run(cmd)


def repair_pdf(old, new):
    # Repair potentially corrupted PDF
    # https://superuser.com/questions/278562/how-can-i-fix-repair-a-corrupted-pdf-file/282056#282056
    subprocess.run(['gs', '-o', new, '-sDEVICE=pdfwrite', '-dPDFSETTINGS=/prepress', old])


def get_height(png_fn, idx, number_of_pages):
    print('Processing {}/{}...'.format(idx + 1, number_of_pages))
    cmd = ['identify', '-ping', '-format', "'%w %h'", '{}-{}'.format(png_fn, idx)]
    print(' '.join(cmd))
    dimension = subprocess.run(cmd, capture_output=True, encoding='utf8').stdout[1:-1]
    return int(dimension.split()[1])


def get_lines(png_fn, png_heights, idx):
    height = png_heights[idx]
    blob = subprocess.run(['convert', '{}-{}'.format(png_fn, idx), '-flatten', '-resize', '1X{}!'.format(height), '-black-threshold', '99%', '-white-threshold', '10%', '-negate', '-morphology', 'Erode', 'Diamond', '-morphology', 'Thinning:-1', 'Skeleton', '-black-threshold', '50%', 'txt:-'], capture_output=True, encoding='utf8').stdout
    lines = []
    for line in blob.splitlines()[1:]:
        if not('#000000' in line):
            lines.append(int(line.split(':')[0].split(',')[1]))
    return lines[offset_top:len(lines) - offset_bottom]


def work(workdir):
    png_fn = os.path.join(workdir, 'pngs')
    pdf_fn = os.path.join(workdir, 'pdf')

    repair_pdf(file, pdf_fn)

    # Reread your existing PDF
    existing_pdf = PdfReader(pdf_fn)

    generate_png(pdf_fn, png_fn)

    png_heights = [get_height(png_fn, i, number_of_pages) for i in range(number_of_pages)]
    lines_per_page = [get_lines(png_fn, png_heights, i) for i in range(number_of_pages)]
    return existing_pdf, png_heights, lines_per_page


def create(png_heights, lines_per_page, existing_pdf):
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
            canvas.drawString(margin_left, int(height - y * height / png_heights[idx]) - baseline_shift, '{}.{}'.format(idx + 1, j + 1))
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
    outputStream = open(file.parents[0] / '{}-with-line-numbers.pdf'.format(filename), 'wb')
    output.write(outputStream)
    outputStream.close()


def main():
    # Read your existing PDF
    existing_pdf = PdfReader(file)
    with tempfile.TemporaryDirectory() as workdir:
        existing_pdf, png_heights, lines_per_page = work(workdir)
        create(png_heights, lines_per_page, existing_pdf)


if __name__ == "__main__":
    main()
