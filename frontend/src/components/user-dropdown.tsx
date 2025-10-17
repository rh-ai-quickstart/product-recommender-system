import { useState } from 'react';
import {
  Dropdown,
  DropdownItem,
  DropdownList,
  MenuToggle,
  type MenuToggleElement,
} from '@patternfly/react-core';
import { UserIcon, SignOutAltIcon } from '@patternfly/react-icons';
import { Link } from '@tanstack/react-router';
import { useAuth, useLogout } from '../hooks/useAuth';

export const UserDropdown: React.FunctionComponent = () => {
  const [isOpen, setIsOpen] = useState(false);
  const { user, isLoading, isAuthenticated } = useAuth();
  const logoutMutation = useLogout();

  const toggle = () => {
    setIsOpen(!isOpen);
  };

  const onSelect = () => {
    setIsOpen(false);
  };

  const handleLogout = () => {
    logoutMutation.mutate();
    onSelect();
  };

  // Don't render if not authenticated or still loading
  if (!isAuthenticated || isLoading) {
    return null;
  }

  // Extract user's first name or use email as fallback
  const displayName = user?.email.split('@')[0] || 'User';

  return (
    <Dropdown
      isOpen={isOpen}
      onSelect={onSelect}
      popperProps={{
        position: 'right',
      }}
      toggle={(toggleRef: React.Ref<MenuToggleElement>) => (
        <MenuToggle
          icon={<UserIcon />}
          ref={toggleRef}
          onClick={toggle}
          aria-label='User menu'
        >
          {displayName}
        </MenuToggle>
      )}
    >
      <DropdownList>
        <DropdownItem
          key='account'
          component={props => (
            <Link to='/account' {...props} onClick={onSelect}>
              My Account
            </Link>
          )}
        />
        <DropdownItem
          key='logout'
          icon={<SignOutAltIcon />}
          onClick={handleLogout}
          isDisabled={logoutMutation.isPending}
        >
          {logoutMutation.isPending ? 'Logging out...' : 'Log out'}
        </DropdownItem>
      </DropdownList>
    </Dropdown>
  );
};
