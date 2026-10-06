"""Protected offline view, private bounded bundle, migration and validation."""

from copy import deepcopy
from io import BytesIO
import base64
from unittest.mock import AsyncMock

from PIL import Image
import pytest

from custom_components.lg_rs232_ip.layout_config import make_layout, element, validate_layout
from custom_components.lg_rs232_ip.layout_library import from_config, validate_library, source_views
from custom_components.lg_rs232_ip.layouts import DisplayLayouts
from custom_components.lg_rs232_ip.startup_design import MAX_IMAGE_BYTES, compact_image
from tests.test_layouts import layouts
from tests.test_layout_cards import cover


@pytest.mark.parametrize('kind', ['hdmi', 'camera', 'weather', 'calendar', 'entity', 'status', 'media', 'message'])
def test_connected_widgets_rejected_in_startup_through_both_document_shapes(kind):
    config = make_layout()
    config['scenes']['startup']['elements'] = [element(kind, 0, 0, 50, 50)]
    with pytest.raises(ValueError):
        validate_layout(config)
    with pytest.raises(ValueError):
        validate_library(from_config(config), make_layout())


@pytest.mark.parametrize('change', [dict(background='solar'), dict(media_background_enabled=True, media_background_entity='media_player.music'), dict(media_background_entity='media_player.music')])
def test_live_backgrounds_cannot_enter_startup(change):
    config = make_layout()
    config['scenes']['startup'].update(change)
    with pytest.raises(ValueError):
        validate_layout(config)
    with pytest.raises(ValueError):
        validate_library(from_config(config), make_layout())


def test_startup_is_protected_but_not_a_source_and_empty_scene_is_allowed():
    config = make_layout()
    library = from_config(config)
    assert 'startup' not in source_views(library)
    startup = next(view for view in library['views'] if view['id'] == 'startup')
    startup['scene']['elements'] = []
    assert validate_library(library, config)[0]['scenes']['startup']['elements'] == []
    library['views'].remove(startup)
    with pytest.raises(ValueError, match='cannot be deleted'):
        validate_library(library, config)


async def test_version_three_upgrade_retains_all_user_views(layouts):
    config = make_layout('morning')
    library = from_config(config)
    library['views'] = [v for v in library['views'] if v['id'] != 'startup']
    custom = deepcopy(library['views'][1]);custom.update(id='view_private', name='Meine Ansicht')
    custom['scene']['elements'][0]['label'] = 'Behalten'
    library['views'].append(custom)
    library['library_version'] = 3
    config['scenes'].pop('startup')
    await layouts.store.async_save(dict(config=config, library=library, revision=13))
    second = DisplayLayouts(layouts.hass, layouts.entry)
    try:
        await second.async_start()
        assert [v for v in second.library['views'] if v['id'] != 'startup'] == library['views']
        assert second.library['library_version'] == 4 and second.revision == 13
        assert 'startup' in second.config['scenes']
    finally:
        await second.async_close()


async def test_offline_bundle_is_scoped_cached_and_contains_only_static_content(layouts):
    config = make_layout()
    image_id = await layouts.backgrounds.async_upload(cover())
    scene = config['scenes']['startup']
    scene.update(background='image', image_id=image_id)
    scene['elements'].append(element('clock', 5, 5, 35, 20))
    config['scenes']['dashboard']['elements'][0]['entity_id'] = ''
    await layouts.async_save(config, 0)
    read = layouts.backgrounds.async_read = AsyncMock(wraps=layouts.backgrounds.async_read)
    bundle = await layouts.startup_design.async_bundle()
    assert bundle['schema'] == 1 and len(bundle['version']) == 64
    assert bundle['image'].startswith('data:image/jpeg;base64,')
    assert len(base64.b64decode(bundle['image'].split(',')[1])) <= MAX_IMAGE_BYTES
    assert not any('entity_id' in item for item in bundle['scene']['elements'])
    assert 'media_background_entity' not in bundle['scene']
    assert await layouts.startup_design.async_bundle() is bundle
    config['scenes']['dashboard']['color'] = '#123456'
    await layouts.async_save(config, 1)
    assert await layouts.startup_design.async_bundle() is bundle
    read.assert_awaited_once_with(image_id)
    config['scenes']['startup']['elements'][0]['text'] = 'Lokaler Start'
    await layouts.async_save(config, 2)
    assert (await layouts.startup_design.async_bundle())['version'] != bundle['version']


def test_background_compression_keeps_4k_when_it_fits_and_strips_metadata():
    image = Image.new('RGB', (3840, 2160), '#123456')
    source = BytesIO();image.save(source, format='JPEG')
    data = base64.b64decode(compact_image(source.getvalue()).split(',')[1])
    with Image.open(BytesIO(data)) as result:
        assert result.size == (3840, 2160) and not result.getexif()
    assert len(data) <= MAX_IMAGE_BYTES


def test_detailed_background_still_fits_offline_budget():
    import random

    # A valid high-detail upload must reduce resolution instead of retrying 503 forever.
    image = Image.frombytes('RGB', (1920, 1080), random.Random(221).randbytes(1920 * 1080 * 3))
    source = BytesIO();image.save(source, format='JPEG', quality=90)
    data = base64.b64decode(compact_image(source.getvalue()).split(',')[1])
    assert len(data) <= MAX_IMAGE_BYTES
    with Image.open(BytesIO(data)) as result:
        assert result.width <= 1920 and result.height <= 1080
