import React from 'react';
import { Listing } from '../services/api';

interface ListingCardProps {
  listing: Listing;
}

const ListingCard: React.FC<ListingCardProps> = ({ listing }) => {
  const defaultImage = 'https://via.placeholder.com/300x200.png?text=No+Image+Available';

  const formatPrice = (price?: number) => {
    if (price === null || price === undefined) return 'Price N/A';
    return `$${price.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
  };

  return (
    <div style={{ border: '1px solid #ddd', borderRadius: '8px', padding: '15px', boxShadow: '0 2px 5px rgba(0,0,0,0.05)', display: 'flex', flexDirection: 'column', justifyContent: 'space-between', height: '100%' }}>
      <div>
        <img
          src={(listing.images && listing.images.length > 0 && listing.images[0]) ? listing.images[0] : defaultImage}
          alt={listing.title || 'Property image'}
          style={{ width: '100%', height: '180px', objectFit: 'cover', borderRadius: '4px', marginBottom: '10px' }}
          onError={(e) => { (e.target as HTMLImageElement).src = defaultImage; }}
        />
        <h3 style={{ marginTop: '0px', marginBottom: '8px', fontSize: '1.15em', lineHeight: '1.3' }}>{listing.title || 'Untitled Listing'}</h3>
        <p style={{ marginBottom: '8px', color: '#007bff', fontWeight: 'bold', fontSize: '1.1em' }}>
          {formatPrice(listing.price_usd)}
        </p>
        <p style={{ marginBottom: '6px', fontSize: '0.95em', color: '#555' }}>
          {listing.location_original || listing.city || listing.address_full || 'Location N/A'}
        </p>
        <p style={{ marginBottom: '6px', fontSize: '0.9em', color: '#777' }}>
          {listing.bedrooms ? `${listing.bedrooms} bed${listing.bedrooms !== 1 ? 's' : ''}` : ''}
          {listing.bedrooms && listing.bathrooms ? ' - ' : ''}
          {listing.bathrooms ? `${listing.bathrooms} bath${listing.bathrooms !== 1 ? 's' : ''}` : ''}
          {listing.area_sqft && (listing.bedrooms || listing.bathrooms) ? ' - ' : ''}
          {listing.area_sqft ? `${listing.area_sqft.toLocaleString()} sqft` : ''}
        </p>
        <p style={{ fontSize: '0.9em', color: '#666', marginBottom: '10px', maxHeight: '60px', overflow: 'hidden', textOverflow: 'ellipsis' }}>
          {listing.description ? listing.description.substring(0, 120) + (listing.description.length > 120 ? '...' : '') : 'No description available.'}
        </p>
      </div>
      <a href={listing.url} target='_blank' rel='noopener noreferrer'
         style={{ display: 'inline-block', marginTop: 'auto', textDecoration: 'none', color: '#007bff', fontWeight: '500', padding: '8px 0' }}>
        View Original Listing &rarr;
      </a>
    </div>
  );
};
export default ListingCard;
