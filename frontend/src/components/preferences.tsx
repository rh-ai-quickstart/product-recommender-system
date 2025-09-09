import {
  ActionGroup,
  Button,
  Card,
  CardTitle,
  Flex,
  FlexItem,
  Grid,
  GridItem,
  Label,
  Skeleton,
} from '@patternfly/react-core';
import { AngleRightIcon, AngleDownIcon } from '@patternfly/react-icons';
import { useState } from 'react';
import { useCategoryTree, useSetPreferences } from '../hooks';
import type { CategoryTree } from '../types';

// Recursive CategoryNode component for hierarchical display (max 3 levels)
interface CategoryNodeProps {
  category: CategoryTree;
  level: number;
  selectedCategories: Set<string>;
  expandedCategories: Set<string>;
  onToggleSelection: (categoryId: string) => void;
  onToggleExpansion: (categoryId: string) => void;
  maxDepth?: number;
}

const CategoryNode: React.FC<CategoryNodeProps> = ({
  category,
  level,
  selectedCategories,
  expandedCategories,
  onToggleSelection,
  onToggleExpansion,
  maxDepth = 3,
}) => {
  const isSelected = selectedCategories.has(category.category_id);
  const isExpanded = expandedCategories.has(category.category_id);
  const hasSubcategories =
    category.subcategories && category.subcategories.length > 0;
  const canShowSubcategories = level < maxDepth - 1; // Allow subcategories only if within depth limit

  return (
    <div style={{ marginLeft: level * 20 }}>
      <Card
        aria-label={`Select ${category.name}`}
        isSelectable
        isSelected={isSelected}
        onClick={() => onToggleSelection(category.category_id)}
        style={{
          marginBottom: 8,
          cursor: 'pointer',
          backgroundColor: isSelected ? '#e7f1ff' : 'white',
          border: isSelected ? '2px solid #0066cc' : '1px solid #d2d2d2',
        }}
      >
        <CardTitle>
          <Flex alignItems={{ default: 'alignItemsCenter' }}>
            <FlexItem>
              {hasSubcategories && canShowSubcategories && (
                <Button
                  variant='plain'
                  onClick={e => {
                    e.stopPropagation(); // Prevent card selection when clicking expand button
                    onToggleExpansion(category.category_id);
                  }}
                  icon={isExpanded ? <AngleDownIcon /> : <AngleRightIcon />}
                  style={{ padding: '4px', marginRight: '8px' }}
                />
              )}
            </FlexItem>
            <FlexItem>
              {category.name}
              {hasSubcategories && !canShowSubcategories && (
                <span
                  style={{
                    fontSize: '0.8em',
                    color: '#666',
                    marginLeft: '8px',
                  }}
                >
                  (+{category.subcategories.length} subcategories)
                </span>
              )}
            </FlexItem>
          </Flex>
        </CardTitle>
      </Card>

      {/* Render subcategories if expanded and within depth limit */}
      {hasSubcategories && isExpanded && canShowSubcategories && (
        <div>
          {category.subcategories.map(subcategory => (
            <CategoryNode
              key={subcategory.category_id}
              category={subcategory}
              level={level + 1}
              selectedCategories={selectedCategories}
              expandedCategories={expandedCategories}
              onToggleSelection={onToggleSelection}
              onToggleExpansion={onToggleExpansion}
              maxDepth={maxDepth}
            />
          ))}
        </div>
      )}
    </div>
  );
};

export function PreferencePage() {
  // Use Set for efficient lookups and independent selection
  const [selectedCategories, setSelectedCategories] = useState<Set<string>>(
    new Set()
  );
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(
    new Set()
  );
  const preferencesMutation = useSetPreferences();
  const [errorMessage, setErrorMessage] = useState('');

  const { data, isLoading, isError } = useCategoryTree();

  // Independent selection logic - parent and child selections are independent
  const handleToggleSelection = (categoryId: string) => {
    setSelectedCategories(prev => {
      const newSelected = new Set(prev);
      if (newSelected.has(categoryId)) {
        newSelected.delete(categoryId);
      } else {
        newSelected.add(categoryId);
      }
      return newSelected;
    });
  };

  // Expand/collapse logic for tree navigation
  const handleToggleExpansion = (categoryId: string) => {
    setExpandedCategories(prev => {
      const newExpanded = new Set(prev);
      if (newExpanded.has(categoryId)) {
        newExpanded.delete(categoryId);
      } else {
        newExpanded.add(categoryId);
      }
      return newExpanded;
    });
  };

  // Clear all selections
  const handleClearSelections = () => {
    setSelectedCategories(new Set());
  };

  // Helper function to get selected categories with both ID and name for tag display
  const getSelectedCategoriesWithDetails = (
    categoryIds: Set<string>,
    categories: CategoryTree[]
  ): Array<{ id: string; name: string }> => {
    const selectedCategories: Array<{ id: string; name: string }> = [];

    const searchCategories = (cats: CategoryTree[]) => {
      for (const cat of cats) {
        if (categoryIds.has(cat.category_id)) {
          selectedCategories.push({
            id: cat.category_id,
            name: cat.name,
          });
        }
        if (cat.subcategories && cat.subcategories.length > 0) {
          searchCategories(cat.subcategories);
        }
      }
    };

    searchCategories(categories);
    return selectedCategories;
  };

  const handleSubmit = async (
    event: React.MouseEvent<HTMLButtonElement, MouseEvent>
  ) => {
    event.preventDefault();

    try {
      setErrorMessage('');

      // Send selected category IDs directly to backend
      const selectedIds = Array.from(selectedCategories);
      console.log('Selected category IDs:', selectedIds);

      await preferencesMutation.mutateAsync({
        category_ids: selectedIds,
      });
    } catch (error) {
      setErrorMessage(
        error instanceof Error
          ? error.message
          : 'Preferences failed to load. Please try again.'
      );
    }
  };

  return (
    <>
      {isLoading ? (
        <Skeleton style={{ height: 200, width: '100%' }} />
      ) : isError ? (
        <div>
          Error fetching preferences:{' '}
          {errorMessage ? errorMessage : 'Unknown error'}
        </div>
      ) : (
        <>
          <div style={{ width: '100%', maxHeight: '60vh', overflowY: 'auto' }}>
            <Grid hasGutter>
              <GridItem span={6}>
                {data?.slice(0, Math.ceil(data.length / 2)).map(category => (
                  <CategoryNode
                    key={category.category_id}
                    category={category}
                    level={0}
                    selectedCategories={selectedCategories}
                    expandedCategories={expandedCategories}
                    onToggleSelection={handleToggleSelection}
                    onToggleExpansion={handleToggleExpansion}
                    maxDepth={3}
                  />
                ))}
              </GridItem>
              <GridItem span={6}>
                {data?.slice(Math.ceil(data.length / 2)).map(category => (
                  <CategoryNode
                    key={category.category_id}
                    category={category}
                    level={0}
                    selectedCategories={selectedCategories}
                    expandedCategories={expandedCategories}
                    onToggleSelection={handleToggleSelection}
                    onToggleExpansion={handleToggleExpansion}
                    maxDepth={3}
                  />
                ))}
              </GridItem>
            </Grid>
          </div>

          {/* Selection summary */}
          {selectedCategories.size > 0 && (
            <div
              style={{
                marginTop: 16,
                padding: 16,
                backgroundColor: '#f8f9fa',
                borderRadius: 8,
              }}
            >
              <Flex
                direction={{ default: 'column' }}
                spaceItems={{ default: 'spaceItemsSm' }}
              >
                <FlexItem>
                  <Flex
                    justifyContent={{ default: 'justifyContentSpaceBetween' }}
                    alignItems={{ default: 'alignItemsCenter' }}
                  >
                    <FlexItem>
                      <strong>
                        Selected categories: {selectedCategories.size}
                      </strong>
                    </FlexItem>
                  </Flex>
                </FlexItem>
                <FlexItem>
                  <Flex wrap='wrap' spaceItems={{ default: 'spaceItemsXs' }}>
                    {data &&
                      getSelectedCategoriesWithDetails(
                        selectedCategories,
                        data
                      ).map(category => (
                        <FlexItem key={category.id}>
                          <Label
                            color='blue'
                            variant='filled'
                            onClose={() => handleToggleSelection(category.id)}
                            closeBtnAriaLabel={`Remove ${category.name}`}
                          >
                            {category.name}
                          </Label>
                        </FlexItem>
                      ))}
                  </Flex>
                </FlexItem>
              </Flex>
            </div>
          )}

          <Flex
            style={{ marginTop: 24 }}
            justifyContent={{ default: 'justifyContentSpaceBetween' }}
          >
            <FlexItem>
              {selectedCategories.size > 0 && (
                <Button variant='secondary' onClick={handleClearSelections}>
                  Clear All Selections
                </Button>
              )}
            </FlexItem>
            <FlexItem>
              <ActionGroup>
                <Button
                  variant='primary'
                  type='submit'
                  onClick={handleSubmit}
                  isDisabled={selectedCategories.size === 0}
                >
                  Submit ({selectedCategories.size} selected)
                </Button>
              </ActionGroup>
            </FlexItem>
          </Flex>
        </>
      )}
    </>
  );
}
