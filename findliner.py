import pathlib, tempfile, subprocess, io, os, click
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib import colors


def repair_pdf(old, new, verbose):
    # Repair potentially corrupted PDF
    # https://superuser.com/questions/278562/how-can-i-fix-repair-a-corrupted-pdf-file/282056#282056
    cmd = ['gs', '-o', new, '-sDEVICE=pdfwrite', '-dPDFSETTINGS=/prepress', old]
    if verbose:
        click.echo(' '.join(cmd))
    result = subprocess.run(cmd)
    if result.returncode != 0:
        raise RuntimeError('gs command failed')


def generate_images(pdf_fn, png_fn_base, has_one_page, verbose):
    # When pdf consists of a single page, imagemagick does not append a counter to the png file
    png_fn_alt = png_fn_base + '-0' if has_one_page else png_fn_base
    cmd = ['convert', pdf_fn, '-strip', f'png:{png_fn_alt}']
    if verbose:
        click.echo(' '.join(cmd))
    result = subprocess.run(cmd)
    if result.returncode != 0:
        raise RuntimeError('convert command failed')

def get_height(png_fn, verbose):
    cmd = ['identify', '-ping', '-format', "'%w %h'", png_fn]
    if verbose:
        click.echo(' '.join(cmd))
    result = subprocess.run(cmd, capture_output=True, encoding='utf8')
    if result.returncode != 0:
        raise RuntimeError('identify command failed')
    dimension = result.stdout[1:-1]
    return int(dimension.split()[1])


def get_lines(png_fn, height, verbose):
    cmd = ['convert', png_fn, '-flatten', '-resize', f'1X{height}!', '-black-threshold', '99%', '-white-threshold', '10%', '-negate', '-morphology', 'Erode', 'Diamond', '-morphology', 'Thinning:-1', 'Skeleton', '-black-threshold', '50%', 'txt:-']
    if verbose:
        click.echo(' '.join(cmd))
    result = subprocess.run(cmd, capture_output=True, encoding='utf8')
    if result.returncode != 0:
        raise RuntimeError('identify command failed')
    blob = result.stdout
    lines = []
    for line in blob.splitlines()[1:]:
        if not('#000000' in line):
            lines.append(int(line.split(':')[0].split(',')[1]))
    return lines


def check_filetype(path_to_file):
    file_extension = pathlib.Path(path_to_file).suffix.lower()

    if file_extension != '.pdf':
        click.echo(f'Can open only PDF. This file type ({file_extension}) is not supported.')
        quit()

def work(path_to_file, work_dir, verbose):
    pdf_fn = os.path.join(work_dir, 'pdf')
    repair_pdf(path_to_file, pdf_fn, verbose)

    # Read the repaired pdf
    existing_pdf = PdfReader(pdf_fn)
    number_of_pages = len(existing_pdf.pages)

    png_fn_base = os.path.join(work_dir, 'png')
    generate_images(pdf_fn, png_fn_base, number_of_pages == 1, verbose)

    png_heights = []
    lines_per_page = []
    with click.progressbar(range(number_of_pages), label='Finding lines of content') as bar:
        for i in bar:
            png_fn = f'{png_fn_base}-{i}'
            height = get_height(png_fn, verbose)
            png_heights.append(height)
            lines_per_page.append(get_lines(png_fn, height, verbose))
    return existing_pdf, png_heights, lines_per_page, number_of_pages


def create(existing_pdf, png_heights, lines_per_page, number_of_pages, path_to_file, offset_top, offset_bottom, margin_left, margin_right, hex_color, font_size, baseline_shift):
    ## Add text to existing PDF using Python
    # https://stackoverflow.com/questions/1180115/add-text-to-existing-pdf-using-python

    # Create a new PDF with Reportlab
    packet = io.BytesIO()
    can = canvas.Canvas(packet)

    with click.progressbar((lines_per_page), label='Writing line numbers') as bar:
        for idx, lines in enumerate(bar):
            page = existing_pdf.pages[idx]
            width = page.mediabox[2]
            height = page.mediabox[3]
            can.setPageSize((width, height))
            can.setFillColor(colors.HexColor(hex_color))
            can.setFont('Courier', font_size)

            reduced_lines = lines[offset_top:len(lines)-offset_bottom]
            # Use margin_right if provided, otherwise use margin_left
            x_position = width - margin_right if margin_right is not None else margin_left
            
            for j, y in enumerate(reduced_lines):
                can.drawString(x_position, int(height - y * height / png_heights[idx]) + baseline_shift, f'{idx + 1}.{j + 1}')
            can.showPage()

    can.save()

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
    path = pathlib.Path(path_to_file).parents[0]
    filename = pathlib.Path(path_to_file).stem
    outputStream = open(path / f'{filename}-with-line-numbers.pdf', 'wb')
    output.write(outputStream)
    outputStream.close()


@click.command()
@click.argument('filename', type=click.Path(exists=True))
@click.option('--offset_top', default=0, help='Ignore the first few lines of content on each page.')
@click.option('--offset_bottom', default=0, help='Ignore the last few lines of content on each page.')
@click.option('--margin_left', default=35, show_default=True, help='Specify the margin on the left of the line numbers')
@click.option('--margin_right', type=int, help='Specify the margin on the right of the line numbers (overrides margin_left)')
@click.option('--hex_color', default='#000000', show_default=True, help='Specify the hex color code of the line numbers')
@click.option('--font_size', default=6, show_default=True, help='Specify the font size of the line numbers')
@click.option('--baseline_shift', default=-2, show_default=True, help='Reposition the baseline of the line numbers')
@click.option('--verbose', is_flag=True, help='Enables verbose mode')
def cli(filename, offset_top, offset_bottom, margin_left, margin_right, hex_color, font_size, baseline_shift, verbose):
    path_to_file = click.format_filename(filename)

    # Check if the filetype is .pdf
    check_filetype(path_to_file)

    # Find the position of each line numbers and the height of each page
    with tempfile.TemporaryDirectory() as work_dir:
        existing_pdf, png_heights, lines_per_page, number_of_pages = work(path_to_file, work_dir, verbose)

    create(existing_pdf, png_heights, lines_per_page, number_of_pages, path_to_file, offset_top, offset_bottom, margin_left, margin_right, hex_color, font_size, baseline_shift)


if __name__ == '__main__':
    cli()
