import {
  Card,
  CardTitle,
  CardBody,
  CardFooter,
  CardHeader,
  Divider,
  Flex,
  FlexItem,
} from '@patternfly/react-core';
import { auto } from '@patternfly/react-core/dist/esm/helpers/Popper/thirdparty/popper-core';
import { StarIcon } from '@patternfly/react-icons';
import type { ProductData } from '../types';

type ProductCardProps = {
  product: ProductData;
  index: number;
};

export const ProductCard: React.FC<ProductCardProps> = ({ product, index }) => {
  const curCardCount = index + 1;
  const cardId = `featured-blog-post-${curCardCount}`;
  const actionId = `card-article-input-${curCardCount}`;
  const cardTitleId = `featured-blog-post-${curCardCount}-title`;

  const price = new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(product.actual_price);
  const rating = new Intl.NumberFormat('en-US', {
    minimumIntegerDigits: 1,
    minimumFractionDigits: 1,
  }).format(product.rating ?? 0);

  return (
    <Card
      id={cardId}
      component='div'
      isClickable
      key={index}
      style={{ height: 400, overflowY: auto }}
    >
      <CardHeader
        className='v6-featured-posts-card-header-img'
        selectableActions={{
          to: `/product/${product.item_id}`,
          selectableActionId: actionId,
          selectableActionAriaLabelledby: cardTitleId,
          name: 'homepage-card',
          isExternalLink: false,
        }}
        style={{
          backgroundImage: `url(${product.img_link})`,
          height: 200,
        }}
      ></CardHeader>
      <Divider />
      <CardTitle id={cardTitleId}>
        <Flex style={{ justifyContent: 'space-between' }}>
          <FlexItem>{product.product_name}</FlexItem>
          <FlexItem>
            {rating} <StarIcon />
          </FlexItem>
        </Flex>
      </CardTitle>
      <CardBody style={{ color: '#707070' }}>{product.about_product}</CardBody>
      <CardFooter style={{ color: '#1F1F1F' }}>{price}</CardFooter>
    </Card>
  );
};
