# Tasks

## 1. VM
- [x] 1.1 `WhiteboardElement`: add `'image'` kind + optional `src`, `fill`, `stroke`, `color`
- [x] 1.2 `addImage(src, x, y, w, h)` and `setStyle(id, {fill?, stroke?, color?})`
- [x] 1.3 vitest: addImage stores src; setStyle updates one element only; both persist via the map

## 2. Component
- [x] 2.1 Image tool: file picker -> data URL -> addImage; render `<image href>`
- [x] 2.2 Render shapes with their fill/stroke/color, defaults when unset
- [x] 2.3 Selected-shape style control (fill + stroke swatches) -> setStyle
- [x] 2.4 e2e: place an image; style a shape's fill and see it applied
