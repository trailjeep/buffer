message('Compiling resources')

about_conf = configuration_data()
about_conf.set('PACKAGE_URL', package_url)
about_conf.set('CONTRIBUTORS', contributors)
about_conf.set('ARTISTS', artists)
about_conf.set('APPID', application_id)
about_conf.set('VERSION', buffer_version + version_suffix)
about_conf.set('COPYRIGHT', copyright)

gnome.compile_resources(
  'resources',
  'resources.gresource.xml',
  gresource_bundle: true,
  source_dir: meson.current_build_dir(),
  install_dir: DATA_DIR,
  install: true,
  dependencies: configure_file (
    input: 'ui/about_dialog.ui.in',
    output: '@BASENAME@',
    configuration: about_conf
  )
)

# Installing the schema file
gschema_conf = configuration_data()
gschema_conf.set('APP_ID', application_id)
gschema_conf.set('GETTEXT_PACKAGE', gettext_package)
configure_file(
    input: '@0@.gschema.xml.in'.format(project_id),
    output: '@0@.gschema.xml'.format(application_id),
    configuration: gschema_conf,
    install: true,
    install_dir: 'share/glib-2.0/schemas'
)

# Validating schemas
compile_schemas = find_program('glib-compile-schemas', required: false)
if compile_schemas.found()
  test('Validate schema file', compile_schemas,
    args: ['--strict', '--dry-run', meson.current_source_dir()]
  )
endif

desktop_conf = configuration_data()
desktop_conf.set('ICON', application_id)
desktop = i18n.merge_file(
  input: configure_file(
    input: files('org.gnome.gitlab.cheywood.Buffer.desktop.in.in'),
    output: 'org.gnome.gitlab.cheywood.Buffer.desktop.in',
    configuration: desktop_conf
  ),
  output: '@0@.desktop'.format(application_id),
  po_dir: join_paths(meson.project_source_root(), 'po'),
  type: 'desktop',
  install: true,
  install_dir: join_paths(get_option('prefix'), get_option('datadir'), 'applications')
)

# Validating the desktop file
desktop_file_validate = find_program('desktop-file-validate', required:false)
if desktop_file_validate.found()
  test (
    'Validate desktop file',
    desktop_file_validate,
    args: join_paths(meson.current_build_dir (), application_id + '.desktop')
  )
endif

metainfo_conf = configuration_data()
metainfo_conf.set('APPID', application_id)
metainfo_conf.set('GETTEXT_PACKAGE', meson.project_name())
metainfo_conf.set('NAME', project_name)
metainfo = i18n.merge_file(
  input: configure_file(
    input: files('org.gnome.gitlab.cheywood.Buffer.metainfo.xml.in.in'),
    output: 'org.gnome.gitlab.cheywood.Buffer.metainfo.xml.in',
    configuration: metainfo_conf
  ),
  output: application_id + '.metainfo.xml',
  install: true,
  install_dir: join_paths(join_paths('share'), 'metainfo'),
  po_dir: join_paths(meson.project_source_root(), 'po')
)


# Validating the metainfo file
#

appstreamcli = find_program('appstreamcli', required: false, disabler: true)
test('Validate appstream file', appstreamcli,
     args: ['validate', '--no-net', '--explain', join_paths(meson.current_build_dir (), application_id + '.metainfo.xml')])

subdir('icons')

install_data('gtksourceview-5/styles/buffer.xml',
  install_dir: get_option('datadir') / 'gtksourceview-5' / 'styles'
)
install_data('gtksourceview-5/styles/buffer-dark.xml',
  install_dir: get_option('datadir') / 'gtksourceview-5' / 'styles'
)
install_data('gtksourceview-5/styles/buffer-high-contrast.xml',
  install_dir: get_option('datadir') / 'gtksourceview-5' / 'styles'
)
install_data('gtksourceview-5/styles/buffer-high-contrast-dark.xml',
  install_dir: get_option('datadir') / 'gtksourceview-5' / 'styles'
)
