export interface ProductData {
  item_id: string;
  product_name: string;
  category: string;
  about_product?: string;
  img_link?: string;
  discount_percentage?: number;
  discounted_price?: number;
  actual_price: number;
  product_link?: string;
  rating_count?: number;
  rating?: number;
}

export interface CartItem {
  user_id: string;
  product_id: string;
  quantity?: number;
}

export interface User {
  user_id: string;
  email: string;
  age: number;
  gender: string;
  signup_date: string; // Changed from date to string to match backend
  preferences: string;
  user_preferences?: CategoryTree[]; // Added structured preferences
  views?: string[]; // Added optional views array
}

// Auth-related types
export interface LoginRequest {
  email: string;
  password: string;
}

export interface SignUpRequest {
  email: string;
  password: string;
  age: number;
  gender: string;
}

export interface AuthResponse {
  user: User;
  token: string;
}

export interface AuthError {
  detail: string;
}

export interface ProductReview {
  id: number;
  productId: string;
  userId?: string;
  rating: number;
  title?: string;
  comment?: string;
  created_at: string;
}

export interface ReviewSummary {
  productId: string;
  count: number;
  avg_rating: number;
}

export interface ReviewSummarization {
  productId: string;
  summary: string;
}

export interface PreferencesRequest {
  category_ids: string[];
}

// Category-related interfaces
export interface CategoryTree {
  category_id: string;
  name: string;
  subcategories: CategoryTree[]; // Recursive structure for nested categories
}

// Query parameters for top products endpoint
export interface TopProductsParams {
  limit?: number; // 1-100, default 10
  include_subcategories?: boolean; // default true
}
