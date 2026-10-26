export const formatPrice = (price?: number | null): string => {
  if (price === undefined || price === null) return "0 so'm";
  return `${price.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ".")} so'm`;
};

export const getMediaUrl = (photo?: string | null): string => {
  if (!photo) return '/api/media/placeholder';
  if (photo.startsWith('http://') || photo.startsWith('https://')) return photo;
  return `/api/media/${photo}`;
};
