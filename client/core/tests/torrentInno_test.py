from torrentInno import TorrentInno
from torrentInno import create_resource_json, create_resource_from_json
from core.common.resource import Resource

client = TorrentInno()

resource_json = create_resource_json('pptx', 'presentation for 5', '~/home/')
resource = create_resource_from_json(resource_json)

TorrentInno.start_share_file('~/home/', resource)