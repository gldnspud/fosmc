import datetime
from operator import itemgetter
import os
from shutil import copytree, rmtree
import sys

import jinja2
from jinja2.exceptions import TemplateNotFound
from slugify import slugify

from fosmc.db import load_data
from fosmc.lint import lint


def main():
    if len(sys.argv) < 3:
        print 'Usage: fosmc-build <DATABASE-PATH> <OUTPUT-PATH> [--force] [name=value]'
        sys.exit(1)
    db_path, output_path = sys.argv[1:3]
    db_path = os.path.abspath(db_path)
    output_path = os.path.abspath(output_path)
    db = load_data(db_path)
    if lint(db):
        print 'Please clean up the lint and try again.'
        sys.exit(1)
    if os.path.isdir(output_path):
        if '--force' not in sys.argv:
            print 'Output path {output_path} exists; use --force to delete.'.format(**locals())
            sys.exit(1)
        else:
            rmtree(output_path)
    # Make directories.
    os.makedirs(output_path)
    for data_type in db:
        os.mkdir(os.path.join(output_path, data_type))
    # Set up templates.
    template_path = os.path.join(db_path, 'templates')
    jinja_env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(template_path),
    )
    jinja_env.filters['list'] = list
    jinja_env.filters['reversed'] = reversed
    # Set up command line variables as globals.
    for arg in sys.argv[3:]:
        if '=' in arg:
            name, value = arg.split('=')
            jinja_env.globals[name.strip()] = value.strip()
    # Common functions.
    def dateformat(date, format='%Y-%m-%d'):
        if isinstance(date, datetime.date):
            return date.strftime(format)
        else:
            return str(date)
    def datesorted(object_list):
        return sorted(
            object_list,
            key=lambda obj: str(obj['date']) if obj.get('date') else None,
        )
    def maybealias(slug, data_type):
        """Convert a slug of an alias to the original slug."""
        return db[data_type][slug].get('alias_for', slug)
    def slugname(slug, data_type):
        """Convert a slug to a name."""
        return db[data_type][slugify(slug.decode('utf8'))]['name']
    def slugobjects(slugs, data_type):
        """Convert a sequence of slugs to objects."""
        return [db[data_type][slug] for slug in slugs]
    jinja_env.filters['dateformat'] = dateformat
    jinja_env.filters['datesorted'] = datesorted
    jinja_env.filters['maybealias'] = maybealias
    jinja_env.filters['slugname'] = slugname
    jinja_env.filters['slugobjects'] = slugobjects
    # Create index file.
    template = jinja_env.get_template('index.html')
    rss_template = jinja_env.get_template('rss.xml')
    recordings_by_date = reversed(datesorted(db['recording'].values()))
    recordings_by_date = [r for r in recordings_by_date if r.get('date')]
    recordings_by_date = recordings_by_date[:10]
    with open(os.path.join(output_path, 'index.html'), 'wb') as f:
        print 'index.html'
        f.write(template.render(
            root='./',
            static='static/',
            recordings_by_date=recordings_by_date,
        ))
    with open(os.path.join(output_path, 'index.xml'), 'wb') as f:
        print 'index.xml'
        f.write(rss_template.render(
            root='./',
            static='static/',
            object_list=recordings_by_date,
            title='Fresh mixes',
            now=datetime.datetime.now(),
        ))
    # Create lists and details.
    for data_type in db:
        # List.
        object_list = sorted(
            db[data_type].itervalues(),
            key=itemgetter('slug'),
        )
        # Only render list if template is available.
        try:
            template = jinja_env.get_template('{data_type}_list.html'.format(**locals()))
        except TemplateNotFound:
            pass
        else:
            output_filename = os.path.join(
                output_path,
                data_type,
                'index.html',
            )
            with open(output_filename, 'wb') as f:
                print '{data_type}/index.html'.format(**locals())
                f.write(template.render(
                    object_list=object_list,
                    root='../',
                    static='../static/',
                ))
        # Details.
        template = jinja_env.get_template('{data_type}.html'.format(**locals()))
        for obj in object_list:
            if 'alias_for' in obj:
                # Don't render aliases.
                continue
            filename = '{slug}.html'.format(**obj)
            output_filename = os.path.join(
                output_path,
                data_type,
                filename,
            )
            with open(output_filename, 'wb') as f:
                print '{data_type}/{filename}'.format(**locals())
                f.write(template.render(
                    obj=obj,
                    root='../',
                    static='../static/',
                ))
            if data_type is not 'recording':
                xml_filename = '{slug}.xml'.format(**obj)
                output_xml_filename = os.path.join(
                    output_path,
                    data_type,
                    xml_filename,
                )
                with open(output_xml_filename, 'wb') as f:
                    print '{data_type}/{xml_filename}'.format(**locals())
                    f.write(rss_template.render(
                        object_list=list(reversed(datesorted(slugobjects(obj.get('recordings', []), 'recording')))),
                        root='../',
                        static='../static/',
                        title=obj['name'],
                        now=datetime.datetime.now(),
                    ))
    # Copy static files.
    print 'static/*'
    static_path = os.path.join(db_path, 'static')
    static_output_path = os.path.join(output_path, 'static')
    copytree(static_path, static_output_path)
    sys.exit(0)


if __name__ == '__main__':
    main()
