project('buffer',
        version: '0.9.5',
        meson_version: '>= 0.59',
        license: 'GPL-3.0-or-later'
       )
i18n = import('i18n')
python = import('python')
gnome = import('gnome')

project_id = 'org.gnome.gitlab.cheywood.Buffer'
project_name = 'Buffer'
package_url = 'https://gitlab.gnome.org/cheywood/buffer'
copyright = '© 2024 Chris Heywood'
contributors = '\n'.join([
    'Chris Heywood',
                        ])
artists = '\n'.join([
                   ])

message('Looking for dependencies')
python_bin = python.find_installation('python3')
if not python_bin.found()
  error('No valid python3 binary found')
else
  message('Found python3 binary')
endif

if not python_bin.language_version().version_compare('>= 3.9')
  error('Python 3.9 or newer is required.')
endif


dependency('glib-2.0', version: '>= 2.76')
dependency('gio-2.0', version: '>= 2.76')
dependency('gobject-introspection-1.0', version: '>=1.66.0')
dependency('gtk4', version: '>=4.16')
dependency('libadwaita-1', version: '>=1.6')
dependency('gtksourceview-5', version: '>= 5.6')

python_dir = python_bin.get_install_dir()
DATA_DIR = join_paths(get_option('prefix'), get_option('datadir'), meson.project_name())
LIBEXEC_DIR = join_paths(get_option('prefix'), get_option('libexecdir'))
bindir = join_paths(get_option('prefix'), get_option('bindir'))


application_id = project_id
if get_option('profile') == 'development'
  profile = 'Devel'
  application_id = '@0@.Devel'.format(application_id)
  vcs_tag = run_command(
    ['git', 'rev-parse', '--short', 'HEAD'],
    check: false
  ).stdout().strip()
  if vcs_tag == ''
    version_suffix = '-devel'
  else
    version_suffix = '-@0@'.format (vcs_tag)
  endif
else
  profile = ''
  version_suffix = ''
endif
buffer_version = meson.project_version()

top_source_dir = meson.current_source_dir()
gettext_package = meson.project_name()

subdir('data')
subdir('po')
subdir('buffer')

gnome.post_install(
  gtk_update_icon_cache: true,
  glib_compile_schemas: true,
  update_desktop_database: true,
)
