// Shrink a photo before uploading (spec A.4): long side at most 2048 px, JPEG.
// A 4 MB phone photo usually becomes ~1 MB, which saves upload time and storage.
export async function compressImage(file, maxSide = 2048, quality = 0.85) {
  try {
    // imageOrientation 'from-image' applies the phone's rotation info (EXIF).
    const bitmap = await createImageBitmap(file, { imageOrientation: 'from-image' })
    const scale = Math.min(1, maxSide / Math.max(bitmap.width, bitmap.height))
    const canvas = document.createElement('canvas')
    canvas.width = Math.round(bitmap.width * scale)
    canvas.height = Math.round(bitmap.height * scale)
    canvas.getContext('2d').drawImage(bitmap, 0, 0, canvas.width, canvas.height)
    return await new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', quality))
  } catch {
    return file // if anything goes wrong, upload the original
  }
}

// Ask the browser to save a Blob as a file (used for the CSV report).
export function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}
