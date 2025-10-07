/**
 * @fileoverview Preferences Onboarding Component
 *
 * This file implements a comprehensive user onboarding system with frontend-only state management.
 *
 * ARCHITECTURE APPROACH:
 * - Frontend-only state management during onboarding process
 * - All selections kept in browser state until final completion
 * - Single batch submission to backend only on completion
 * - No intermediate backend calls during round navigation
 *
 * ONBOARDING FLOW:
 * 1. Category Selection: Users select categories they're interested in
 * 2. Product Selection: 3 rounds of product selection (10-12 products per round)
 * 3. Round Navigation: Users can freely navigate between rounds
 * 4. Completion: Submit all selections when user has selected ≥10 products total
 *
 * KEY BENEFITS:
 * - Perfect navigation experience (no lost selections)
 * - Accurate progress tracking (no double counting)
 * - Predictable state management (single source of truth)
 * - Atomic completion (all or nothing submission)
 */

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
  Alert,
  Spinner,
  Title,
} from '@patternfly/react-core';
import {
  AngleRightIcon,
  AngleDownIcon,
  CheckCircleIcon,
} from '@patternfly/react-icons';
import { useState } from 'react';
import { useCategoryTree } from '../hooks';
import {
  useOnboardingProducts,
  useSubmitOnboardingSelections,
} from '../hooks/useOnboarding';
import { setPreferences } from '../services/preferences';
import { SelectableProductGallery } from './selectable-product-gallery';
import type { CategoryTree, OnboardingStep } from '../types';
import { useNavigate } from '@tanstack/react-router';
import { useQueryClient } from '@tanstack/react-query';

// === ONBOARDING CONSTANTS ===
const ONBOARDING_CONFIG = {
  TARGET_SELECTIONS: 10,
  MAX_ROUNDS: 3,
  PRODUCTS_PER_ROUND: 12,
} as const;

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

/**
 * PreferencePage Component - Handles user onboarding through category and product selection.
 *
 * This component implements a frontend-only state management approach for onboarding:
 * 1. Users select categories they're interested in
 * 2. Users navigate through 3 rounds of product selection (12 products per round)
 * 3. All selections are kept in frontend state until final completion
 * 4. Only on completion are all selections submitted to backend as a batch
 *
 * Key Features:
 * - Multi-round product selection with navigation between rounds
 * - Persistent selection state across round navigation
 * - Progress tracking based on frontend state only
 * - Batch submission of all selections on completion
 *
 * @returns {JSX.Element} The preferences onboarding interface
 */
export function PreferencePage() {
  // Onboarding step management
  const [onboardingStep, setOnboardingStep] =
    useState<OnboardingStep>('categories');
  const [currentRound, setCurrentRound] = useState(1);

  // Category selection state (existing)
  const [selectedCategories, setSelectedCategories] = useState<Set<string>>(
    new Set()
  );
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(
    new Set()
  );

  // Multi-round product selection state
  const [roundSelections, setRoundSelections] = useState<
    Map<number, Set<string>>
  >(
    new Map([
      [1, new Set<string>()],
      [2, new Set<string>()],
      [3, new Set<string>()],
    ])
  );

  // Current round's selected products (derived from roundSelections)
  const selectedProducts = roundSelections.get(currentRound) || new Set();

  /**
   * Calculates the total number of products selected across all rounds.
   * Used for progress tracking and completion validation in frontend-only state management.
   * @returns {number} Total count of selected products across all rounds
   */
  const getTotalRoundSelections = () => {
    let total = 0;
    roundSelections.forEach(selections => {
      total += selections.size;
    });
    return total;
  };

  // Hooks
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const onboardingProductsQuery = useOnboardingProducts(
    currentRound,
    onboardingStep === 'products'
  );
  const submitSelectionsMutation = useSubmitOnboardingSelections();
  // Note: Removed onboardingStatusQuery - we use only frontend state now

  // Error state
  const [errorMessage, setErrorMessage] = useState('');

  const {
    data: categoryData,
    isLoading: categoriesLoading,
    isError: categoriesError,
  } = useCategoryTree();

  // Note: Removed useEffect for onboarding status - we manage completion in frontend

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

  // Category submission handler (modified to go to products step)
  const handleCategorySubmit = async (
    event: React.MouseEvent<HTMLButtonElement, MouseEvent>
  ) => {
    event.preventDefault();

    try {
      setErrorMessage('');

      // Send selected category IDs directly to backend
      const selectedIds = Array.from(selectedCategories);
      console.log('Selected category IDs:', selectedIds);

      // Call setPreferences directly without navigation
      await setPreferences({
        category_ids: selectedIds,
      });

      // Invalidate onboarding products query to ensure fresh data is fetched
      // after category preferences are saved
      queryClient.invalidateQueries({
        queryKey: ['onboardingProducts'],
      });

      // Move to products step
      setOnboardingStep('products');
    } catch (error) {
      setErrorMessage(
        error instanceof Error
          ? error.message
          : 'Preferences failed to load. Please try again.'
      );
    }
  };

  /**
   * Handles product selection/deselection for the current round.
   * Updates the roundSelections Map to persist selections across round navigation.
   * This is part of our frontend-only state management approach.
   * @param {string} productId - The ID of the product being selected/deselected
   * @param {boolean} selected - Whether the product is being selected (true) or deselected (false)
   */
  const handleProductSelection = (productId: string, selected: boolean) => {
    setRoundSelections(prev => {
      const newRoundSelections = new Map(prev);
      const currentRoundSet = new Set(
        newRoundSelections.get(currentRound) || new Set<string>()
      );

      if (selected) {
        currentRoundSet.add(productId);
      } else {
        currentRoundSet.delete(productId);
      }

      newRoundSelections.set(currentRound, currentRoundSet);
      return newRoundSelections;
    });
  };

  const handleSelectAllProducts = () => {
    if (onboardingProductsQuery.data?.products) {
      const allProductIds = onboardingProductsQuery.data.products.map(
        p => p.item_id
      );
      setRoundSelections(prev => {
        const newRoundSelections = new Map(prev);
        const currentRoundSet = new Set(
          newRoundSelections.get(currentRound) || new Set<string>()
        );
        allProductIds.forEach(id => currentRoundSet.add(id));
        newRoundSelections.set(currentRound, currentRoundSet);
        return newRoundSelections;
      });
    }
  };

  const handleClearAllProducts = () => {
    setRoundSelections(prev => {
      const newRoundSelections = new Map(prev);
      newRoundSelections.set(currentRound, new Set<string>());
      return newRoundSelections;
    });
  };

  /**
   * Navigates to the next round without submitting selections to backend.
   * Selections are preserved in frontend state for later batch submission.
   * Part of our frontend-only state management approach.
   */
  const handleNextRound = () => {
    // Move to next round (selections preserved in roundSelections)
    // No backend submission - all selections stay in frontend until completion
    setCurrentRound(prev => prev + 1);
  };

  /**
   * Submits all product selections from all rounds as a single batch to the backend.
   * This is the only point where selections are sent to the server in our frontend-only approach.
   * Collects all selections from roundSelections Map and submits them together.
   * Only submits if user has selected at least 10 products total.
   */
  const handleCompleteOnboarding = async () => {
    try {
      setErrorMessage('');

      // Collect all selections from all rounds
      const allSelectedProducts: string[] = [];
      roundSelections.forEach(selections => {
        selections.forEach(productId => {
          allSelectedProducts.push(productId);
        });
      });

      // Submit all selections as one batch (use round 1 as placeholder since we're submitting all)
      const response = await submitSelectionsMutation.mutateAsync({
        selected_product_ids: allSelectedProducts,
        round_number: 1, // Placeholder - we're submitting all rounds at once
      });

      if (
        response.is_complete ||
        allSelectedProducts.length >= ONBOARDING_CONFIG.TARGET_SELECTIONS
      ) {
        setOnboardingStep('complete');
      }
    } catch (error) {
      setErrorMessage(
        error instanceof Error
          ? error.message
          : 'Failed to complete onboarding. Please try again.'
      );
    }
  };

  // Round navigation handlers
  const handlePreviousRound = () => {
    if (currentRound > 1) {
      setCurrentRound(prev => prev - 1);
    }
  };

  const handleBackToCategories = () => {
    setOnboardingStep('categories');
    setCurrentRound(1);
    setRoundSelections(
      new Map([
        [1, new Set<string>()],
        [2, new Set<string>()],
        [3, new Set<string>()],
      ])
    );
  };

  const handleFinishOnboarding = () => {
    // Force invalidation of all recommendation-related queries
    queryClient.invalidateQueries({ queryKey: ['recommendations'] });
    queryClient.invalidateQueries({ queryKey: ['currentUser'] });

    navigate({ to: '/' });
  };

  // Conditional rendering based on onboarding step
  if (onboardingStep === 'categories') {
    return (
      <>
        <Title headingLevel='h1' size='2xl' style={{ marginBottom: 24 }}>
          Choose Your Interests
        </Title>
        <p style={{ marginBottom: 24, color: '#666', fontSize: '1.1rem' }}>
          Select the categories you're interested in. We'll use these to show
          you relevant products.
        </p>

        {categoriesLoading ? (
          <Skeleton style={{ height: 200, width: '100%' }} />
        ) : categoriesError ? (
          <Alert variant='danger' title='Error loading categories'>
            {errorMessage || 'Failed to load categories. Please try again.'}
          </Alert>
        ) : (
          <>
            <div
              style={{ width: '100%', maxHeight: '60vh', overflowY: 'auto' }}
            >
              <Grid hasGutter>
                <GridItem span={6}>
                  {categoryData
                    ?.slice(0, Math.ceil(categoryData.length / 2))
                    .map(category => (
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
                  {categoryData
                    ?.slice(Math.ceil(categoryData.length / 2))
                    .map(category => (
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
                      {categoryData &&
                        getSelectedCategoriesWithDetails(
                          selectedCategories,
                          categoryData
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

            {errorMessage && (
              <Alert variant='danger' title='Error' style={{ marginTop: 16 }}>
                {errorMessage}
              </Alert>
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
                    onClick={handleCategorySubmit}
                    isDisabled={selectedCategories.size === 0}
                  >
                    Next: Select Products ({selectedCategories.size} categories)
                  </Button>
                </ActionGroup>
              </FlexItem>
            </Flex>
          </>
        )}
      </>
    );
  }

  if (onboardingStep === 'products') {
    const targetSelections = ONBOARDING_CONFIG.TARGET_SELECTIONS;
    const currentRoundSelected = selectedProducts.size;
    const totalRoundSelections = getTotalRoundSelections();
    const canProceed = totalRoundSelections >= targetSelections;
    const isLastRound = currentRound >= ONBOARDING_CONFIG.MAX_ROUNDS;

    return (
      <>
        <Flex
          justifyContent={{ default: 'justifyContentSpaceBetween' }}
          alignItems={{ default: 'alignItemsCenter' }}
          style={{ marginBottom: 24 }}
        >
          <FlexItem>
            <Title headingLevel='h1' size='2xl'>
              Personalize Your Recommendations
            </Title>
          </FlexItem>
          <FlexItem>
            <Button variant='link' onClick={handleBackToCategories}>
              ← Back to Categories
            </Button>
          </FlexItem>
        </Flex>

        {onboardingProductsQuery.isLoading ? (
          <div style={{ textAlign: 'center', padding: '2rem' }}>
            <Spinner size='lg' />
            <p style={{ marginTop: 16 }}>Loading products...</p>
          </div>
        ) : onboardingProductsQuery.isError ? (
          <Alert variant='danger' title='Error loading products'>
            Failed to load products. Please try again.
          </Alert>
        ) : (
          <>
            <SelectableProductGallery
              products={onboardingProductsQuery.data?.products || []}
              selectedProducts={selectedProducts}
              onSelectionChange={handleProductSelection}
              totalSelected={totalRoundSelections}
              targetSelections={targetSelections}
              onSelectAll={handleSelectAllProducts}
              onClearAll={handleClearAllProducts}
            />

            {errorMessage && (
              <Alert variant='danger' title='Error' style={{ marginTop: 16 }}>
                {errorMessage}
              </Alert>
            )}

            <Flex
              style={{
                marginTop: 32,
                padding: '16px 0',
                borderTop: '1px solid #d2d2d2',
              }}
              justifyContent={{ default: 'justifyContentSpaceBetween' }}
            >
              <FlexItem>
                <ActionGroup>
                  <Button variant='secondary' onClick={handleBackToCategories}>
                    ← Back to Categories
                  </Button>
                  {currentRound > 1 && (
                    <Button variant='secondary' onClick={handlePreviousRound}>
                      ← Previous Round
                    </Button>
                  )}
                </ActionGroup>
              </FlexItem>
              <FlexItem>
                <ActionGroup>
                  {!isLastRound && (
                    <Button
                      variant='secondary'
                      onClick={handleNextRound}
                      isDisabled={currentRoundSelected === 0}
                    >
                      Next Round ({currentRoundSelected} selected)
                    </Button>
                  )}
                  <Button
                    variant='primary'
                    onClick={handleCompleteOnboarding}
                    isDisabled={!canProceed}
                    isLoading={submitSelectionsMutation.isPending}
                  >
                    Complete Onboarding ({totalRoundSelections} total)
                  </Button>
                </ActionGroup>
              </FlexItem>
            </Flex>
          </>
        )}
      </>
    );
  }

  if (onboardingStep === 'complete') {
    return (
      <div style={{ textAlign: 'center', padding: '3rem 1rem' }}>
        <CheckCircleIcon
          style={{
            fontSize: '4rem',
            color: '#27ae60',
            marginBottom: '1.5rem',
          }}
        />
        <Title headingLevel='h1' size='2xl' style={{ marginBottom: 16 }}>
          Onboarding Complete!
        </Title>
        <p
          style={{
            fontSize: '1.2rem',
            color: '#666',
            marginBottom: 32,
            maxWidth: '600px',
            margin: '0 auto 32px',
          }}
        >
          Great job! You've selected {getTotalRoundSelections()} products. We'll
          use your preferences to show you personalized recommendations.
        </p>

        <ActionGroup>
          <Button variant='primary' size='lg' onClick={handleFinishOnboarding}>
            Start Exploring Products
          </Button>
        </ActionGroup>
      </div>
    );
  }

  return null;
}
