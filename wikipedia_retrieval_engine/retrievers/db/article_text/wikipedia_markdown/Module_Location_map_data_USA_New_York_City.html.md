# Location map/data/USA New York City

Module documentation[[view](/wiki/Module:Location_map/data/USA_New_York_City/doc)] [(/wiki/Special:EditPage/Module:Location_map/data/USA_New_York_City/doc)] [[history](/wiki/Special:PageHistory/Module:Location_map/data/USA_New_York_City/doc)] [[purge](/wiki/Special:Purge/Module:Location_map/data/USA_New_York_City)]

Location map of New York City

|  |  |  |  |
| --- | --- | --- | --- |
| name | New York City | | |
| border coordinates |
| 40.92 | | |
| -74.27 | ←↕→ | -73.68 |
| 40.49 | | |
| map center | [40°42′18″N 73°58′30″W / 40.705°N 73.975°W / 40.705; -73.975](https://geohack.toolforge.org/geohack.php?pagename=Module:Location_map/data/USA_New_York_City&params=40.705_N_73.975_W_) | | | |
| image | `USA_New_York_City_location_map.svg` | | |
|  | | | |

**Module:Location map/data/USA New York City** is a location map definition used to overlay markers and labels on an [equirectangular projection](/wiki/Equirectangular_projection) map of [New York City](/wiki/New_York_City). The markers are placed by [latitude](/wiki/Latitude) and [longitude](/wiki/Longitude) coordinates on the default map or a similar map image.

## Usage

These definitions are used by the following templates when invoked with parameter "USA New York City":

- `{{Location map|USA New York City |...}}`
- `{{Location map many|USA New York City |...}}`
- `{{Location map+|USA New York City |...}}`
- `{{Location map~|USA New York City |...}}`

## Map definition

- `name = New York City`

  :   Name used in the default map caption

- `image = USA_New_York_City_location_map.svg`

  :   The default map image, without "Image:" or "File:"

- `top = 40.92`

  :   [Latitude](/wiki/Latitude) at top edge of map, in [decimal degrees](/wiki/Decimal_degrees)

- `bottom = 40.49`

  :   Latitude at bottom edge of map, in decimal degrees

- `left = -74.27`

  :   [Longitude](/wiki/Longitude) at left edge of map, in decimal degrees

- `right = -73.68`

  :   Longitude at right edge of map, in decimal degrees

## Precision

[Longitude](/wiki/Longitude): from West to East this map definition covers 0.59 degrees.

- At an image width of 200 [pixels](/wiki/Pixel), that is 0.0029 degrees per pixel.
- At an image width of 1000 pixels, that is 0.0006 degrees per pixel.

[Latitude](/wiki/Latitude): from North to South this map definition covers 0.43 degrees.

- At an image height of 200 pixels, that is 0.0022 degrees per pixel.
- At an image height of 1000 pixels, that is 0.0004 degrees per pixel.

## See also

- [Module:Location map/data/USA](/wiki/Module:Location_map/data/USA)
- [Module:Location map/data/USA New York](/wiki/Module:Location_map/data/USA_New_York)

### Location map templates

- [Template:Location map](/wiki/Template:Location_map), to display one mark and label using latitude and longitude
- [Template:Location map many](/wiki/Template:Location_map_many), to display up to nine marks and labels
- [Template:Location map+](/wiki/Template:Location_map%2B), to display an unlimited number of marks and labels

### Creating new map definitions

- [Template:Location map/Creating a new map definition](/wiki/Template:Location_map/Creating_a_new_map_definition)

The above [documentation](/wiki/Wikipedia:Template_documentation) is [transcluded](/wiki/Help:Transclusion) from [Module:Location map/data/USA New York City/doc](/wiki/Module:Location_map/data/USA_New_York_City/doc). ((/wiki/Special:EditPage/Module:Location_map/data/USA_New_York_City/doc) | [history](/wiki/Special:PageHistory/Module:Location_map/data/USA_New_York_City/doc))
Editors can experiment in this module's sandbox ([create](https://en.wikipedia.org/w/index.php?title=Module:Location_map/data/USA_New_York_City/sandbox&action=edit&preload=Template%3ADocumentation%2Fpreload-module-sandbox) | [mirror](https://en.wikipedia.org/w/index.php?title=Module:Location_map/data/USA_New_York_City/sandbox&preload=Module%3ALocation+map%2Fdata%2FUSA+New+York+City&action=edit&summary=Create+sandbox+version+of+%5B%5BModule%3ALocation+map%2Fdata%2FUSA+New+York+City%5D%5D)) and testcases ([create](https://en.wikipedia.org/w/index.php?title=Module:Location_map/data/USA_New_York_City/testcases&action=edit&preload=Template%3ADocumentation%2Fpreload-module-testcases)) pages.
 [Subpages of this module](/wiki/Special:PrefixIndex/Module:Location_map/data/USA_New_York_City/).

```
return {
	name = 'New York City',
	top = 40.92,
	bottom = 40.49,
	left = -74.27,
	right = -73.68,
	width = 200,
	image = 'USA_New_York_City_location_map.svg'
}
```
