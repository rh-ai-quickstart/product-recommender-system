import { Card, CardBody, Button, Flex, FlexItem } from '@patternfly/react-core';
import { TrashIcon } from '@patternfly/react-icons';
import { useAuth } from '../contexts/AuthProvider';
import { useCart, useRemoveFromCart, useUpdateCart } from '../hooks/useCart';
import { useProduct } from '../hooks/useProducts';
import { useState, useEffect } from 'react';
interface CartDropdownProps {
  isOpen: boolean;
  onClose: () => void;
}

// Helper function to generate consistent prices based on product ID
const hash = (str: string): number => {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i);
    hash = (hash << 5) - hash + char;
    hash = hash & hash; // Convert to 32-bit integer
  }
  return Math.abs(hash);
};

// Helper component to render a single cart item with product details
const CartItemRow = ({
  item,
  index,
  cartItemsLength,
  onQuantityChange,
  onRemoveItem,
  isRemoving,
  isUpdating,
  onPriceCalculated,
}: any) => {
  const { data: productData, isLoading: isProductLoading } = useProduct(
    item.product_id
  );
  const quantity = item.quantity || 1;

  // Use product name if available, fallback to product ID
  const displayName = productData?.product_name || `Product ${item.product_id}`;

  // Use real product price, fallback to hash-based price if product data not loaded
  const itemPrice =
    productData?.actual_price ?? (hash(item.product_id) % 40) + 10;

  // Report the calculated price back to parent for total calculation
  useEffect(() => {
    if (productData?.actual_price && onPriceCalculated) {
      onPriceCalculated(item.product_id, productData.actual_price, quantity);
    }
  }, [productData?.actual_price, quantity, item.product_id, onPriceCalculated]);

  return (
    <div
      key={`${item.product_id}-${index}`}
      style={{
        padding: '12px 0',
        borderBottom:
          index < cartItemsLength - 1 ? '1px solid #f0f0f0' : 'none',
        opacity: isRemoving || isUpdating ? 0.5 : 1,
        transition: 'opacity 0.2s',
      }}
    >
      <Flex alignItems={{ default: 'alignItemsCenter' }}>
        <FlexItem flex={{ default: 'flex_1' }}>
          <div style={{ fontSize: '14px', fontWeight: '500' }}>
            {isProductLoading ? 'Loading...' : displayName}
          </div>

          {/* Quantity Controls */}
          <div
            style={{
              fontSize: '12px',
              color: '#6a6e73',
              marginTop: '4px',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
            }}
          >
            <span>Price: ${itemPrice.toFixed(2)}</span>

            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                border: '1px solid #d2d2d2',
                borderRadius: '4px',
                padding: '2px',
              }}
            >
              {/* Minus Button */}
              <Button
                variant='plain'
                aria-label='Decrease quantity'
                onClick={() => onQuantityChange(item.product_id, quantity - 1)}
                isDisabled={isUpdating || isRemoving || quantity <= 1}
                style={{
                  padding: '2px 6px',
                  minHeight: 'auto',
                  fontSize: '14px',
                  lineHeight: 1,
                }}
              >
                −
              </Button>

              {/* Quantity Display */}
              <span
                style={{
                  minWidth: '20px',
                  textAlign: 'center',
                  fontSize: '12px',
                  fontWeight: '500',
                }}
              >
                {quantity}
              </span>

              {/* Plus Button */}
              <Button
                variant='plain'
                aria-label='Increase quantity'
                onClick={() => onQuantityChange(item.product_id, quantity + 1)}
                isDisabled={isUpdating || isRemoving}
                style={{
                  padding: '2px 6px',
                  minHeight: 'auto',
                  fontSize: '14px',
                  lineHeight: 1,
                }}
              >
                +
              </Button>
            </div>
          </div>
        </FlexItem>

        <FlexItem>
          <div
            style={{
              fontSize: '14px',
              fontWeight: 'bold',
              marginRight: '8px',
            }}
          >
            ${(itemPrice * quantity).toFixed(2)}
          </div>
        </FlexItem>

        <FlexItem>
          {/* Remove button */}
          <Button
            variant='plain'
            aria-label={`Remove ${displayName} from cart`}
            onClick={() => onRemoveItem(item.product_id)}
            isLoading={isRemoving}
            isDisabled={isRemoving || isUpdating}
            style={{
              padding: '4px',
              minHeight: 'auto',
              color: '#c9190b',
            }}
          >
            {isRemoving ? (
              <span style={{ fontSize: '12px' }}>...</span>
            ) : (
              <TrashIcon size={12} />
            )}
          </Button>
        </FlexItem>
      </Flex>
    </div>
  );
};

export const CartDropdown = ({ isOpen, onClose }: CartDropdownProps) => {
  const { user } = useAuth();
  const userId = user?.user_id || '';
  const { data: cartItems, isLoading } = useCart(userId);
  const removeFromCartMutation = useRemoveFromCart();
  const updateCartMutation = useUpdateCart();

  // Track real prices for total calculation
  const [itemPrices, setItemPrices] = useState<
    Record<string, { price: number; quantity: number }>
  >({});

  // Reset itemPrices when cart changes
  useEffect(() => {
    if (cartItems) {
      // Remove prices for items that are no longer in the cart
      setItemPrices(prev => {
        const newPrices = { ...prev };
        // Keep only prices for items that are still in the cart
        Object.keys(newPrices).forEach(productId => {
          if (!cartItems.find(item => item.product_id === productId)) {
            delete newPrices[productId];
          }
        });
        return newPrices;
      });
    }
  }, [cartItems]);

  const handlePriceCalculated = (
    productId: string,
    price: number,
    quantity: number
  ) => {
    setItemPrices(prev => ({
      ...prev,
      [productId]: { price, quantity },
    }));
  };

  // Calculate total using real prices and current cart quantities
  const calculateRealCartTotal = (): number => {
    if (!cartItems) return 0;

    return cartItems.reduce((total, cartItem) => {
      const priceInfo = itemPrices[cartItem.product_id];
      if (priceInfo) {
        // Use the current cart quantity, not the stored quantity
        return total + priceInfo.price * cartItem.quantity;
      }
      return total;
    }, 0);
  };

  if (!isOpen) return null;

  const handleQuantityChange = (productId: string, newQuantity: number) => {
    if (newQuantity <= 0) {
      // If quantity becomes 0 or less, remove the item
      handleRemoveItem(productId);
      return;
    }

    console.log('📝 Updating quantity:', { productId, newQuantity });
    updateCartMutation.mutate(
      {
        user_id: userId,
        product_id: productId,
        quantity: newQuantity,
      },
      {
        onSuccess: () => {
          console.log('✅ Quantity updated successfully');
        },
        onError: error => {
          console.log('❌ Failed to update quantity:', error);
        },
      }
    );
  };

  const handleRemoveItem = (productId: string) => {
    console.log('🗑️ Removing entire item:', productId);
    removeFromCartMutation.mutate(
      {
        user_id: userId,
        product_id: productId,
        quantity: 1, // Not used for delete, but required by interface
      },
      {
        onSuccess: () => {
          console.log('✅ Item removed successfully');
        },
        onError: error => {
          console.log('❌ Failed to remove item:', error);
        },
      }
    );
  };

  return (
    <>
      {/* Backdrop to close dropdown when clicking outside */}
      <div
        style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'transparent',
          zIndex: 999,
        }}
        onClick={onClose}
      />

      {/* Cart dropdown */}
      <Card
        style={{
          position: 'absolute',
          top: '100%',
          right: 0,
          width: '320px',
          maxHeight: '400px',
          overflow: 'auto',
          zIndex: 1000,
          marginTop: '8px',
          boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
          border: '1px solid #d2d2d2',
        }}
      >
        <CardBody>
          <div style={{ marginBottom: '16px' }}>
            <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 'bold' }}>
              🛒 Your Cart ({cartItems?.length || 0} items)
            </h3>
          </div>

          {isLoading ? (
            <div style={{ textAlign: 'center', padding: '20px' }}>
              Loading cart...
            </div>
          ) : cartItems?.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '20px' }}>
              <p style={{ margin: 0, color: '#6a6e73' }}>Your cart is empty</p>
              <p
                style={{
                  margin: '8px 0 0 0',
                  fontSize: '14px',
                  color: '#6a6e73',
                }}
              >
                Add some products to get started!
              </p>
            </div>
          ) : (
            <>
              {/* Cart Items */}
              <div style={{ marginBottom: '16px' }}>
                {cartItems?.map((item, index) => {
                  const isRemoving =
                    removeFromCartMutation.isPending &&
                    removeFromCartMutation.variables?.product_id ===
                      item.product_id;
                  const isUpdating =
                    updateCartMutation.isPending &&
                    updateCartMutation.variables?.product_id ===
                      item.product_id;

                  return (
                    <CartItemRow
                      key={`${item.product_id}-${index}`}
                      item={item}
                      index={index}
                      cartItemsLength={cartItems.length}
                      onQuantityChange={handleQuantityChange}
                      onRemoveItem={handleRemoveItem}
                      onPriceCalculated={handlePriceCalculated}
                      isRemoving={isRemoving}
                      isUpdating={isUpdating}
                    />
                  );
                })}
              </div>

              {/* Cart Total - Use real prices */}
              <div
                style={{
                  padding: '12px 0',
                  borderTop: '2px solid #f0f0f0',
                  marginBottom: '16px',
                }}
              >
                <Flex alignItems={{ default: 'alignItemsCenter' }}>
                  <FlexItem flex={{ default: 'flex_1' }}>
                    <span style={{ fontWeight: 'bold', fontSize: '16px' }}>
                      Total:
                    </span>
                  </FlexItem>
                  <FlexItem>
                    <span style={{ fontWeight: 'bold', fontSize: '16px' }}>
                      ${calculateRealCartTotal().toFixed(2)}
                    </span>
                  </FlexItem>
                </Flex>
              </div>
            </>
          )}

          {/* Action Buttons */}
          <Flex
            direction={{ default: 'column' }}
            spaceItems={{ default: 'spaceItemsSm' }}
          >
            <FlexItem>
              <Button
                variant='primary'
                style={{ width: '100%' }}
                isDisabled={!cartItems?.length}
                onClick={() => {
                  alert('In a production app, this is where users will be led to a billing page.');
                  onClose();
                }}
              >
                Checkout ({cartItems?.length || 0} items)
              </Button>
            </FlexItem>
          </Flex>
        </CardBody>
      </Card>
    </>
  );
};
