import {
  Form,
  FormGroup,
  TextInput,
  ActionGroup,
  Button,
  Radio,
  LoginPage,
  LoginMainFooterBandItem,
  InputGroup,
  InputGroupItem,
  Alert,
} from '@patternfly/react-core';
import { Link } from '@tanstack/react-router';
import { useForm } from '@tanstack/react-form';
import { EyeIcon, EyeSlashIcon, PaperPlaneIcon } from '@patternfly/react-icons';
import { useState } from 'react';
import { useSignup } from '../hooks/useAuth';
import { authService } from '../services/auth';

export const SimpleSignupPage: React.FunctionComponent = () => {
  // const navigate = useNavigate();
  const signupMutation = useSignup();
  const [passwordHidden, setPasswordHidden] = useState(true);
  const [errorMessage, setErrorMessage] = useState('');
  const hidePasswordAriaLabel = 'Hide password';
  const showPasswordAriaLabel = 'Show password';

  const form = useForm({
    // Set default values for your form fields
    defaultValues: {
      email: '',
      password: '',
      display_name: '',
      age: '',
      gender: '',
    },
    // This function is called on successful submission
    onSubmit: async ({ value }) => {
      try {
        setErrorMessage('');
        await signupMutation.mutateAsync({
          email: value.email,
          password: value.password,
          display_name: value.display_name,
          age: parseInt(value.age),
          gender: value.gender,
        });
      } catch (error) {
        setErrorMessage(
          error instanceof Error
            ? error.message
            : 'Signup failed. Please try again.'
        );
      }
    },
  });

  const handleCancel = () => {
    form.reset();
  };

  const signupForm = (
    <>
      {errorMessage && (
        <Alert
          variant='danger'
          title='Signup Error'
          style={{ marginBottom: '1rem' }}
        >
          {errorMessage}
        </Alert>
      )}
      <Form
        isWidthLimited
        onSubmit={e => {
          e.preventDefault();
          e.stopPropagation();
          void form.handleSubmit();
        }}
      >
        <form.Field
          name='email'
          validators={{
            onChange: ({ value }) => {
              if (!value) {
                return 'Email is required';
              }
              if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) {
                return 'Please enter a valid email address';
              }
              return undefined;
            },
          }}
        >
          {field => (
            <FormGroup label='Email' isRequired fieldId='simple-form-email-02'>
              <TextInput
                isRequired
                type='email'
                id='simple-form-email-02'
                name={field.name}
                value={field.state.value}
                onChange={(_event, value) => field.handleChange(value)}
                validated={
                  !field.state.meta.isTouched
                    ? 'default'
                    : field.state.meta.errors.length > 0
                      ? 'error'
                      : 'success'
                }
              />
              {field.state.meta.errors.length > 0 && (
                <div
                  style={{
                    color: '#c9190b',
                    fontSize: '14px',
                    marginTop: '4px',
                  }}
                >
                  {field.state.meta.errors[0]}
                </div>
              )}
            </FormGroup>
          )}
        </form.Field>
        <form.Field
          name='display_name'
          validators={{
            onChange: ({ value }) => {
              if (!value) {
                return 'Display name is required';
              }
              if (value.length < 2) {
                return 'Display name must be at least 2 characters';
              }
              if (value.length > 50) {
                return 'Display name must be 50 characters or less';
              }
              return undefined;
            },
            onChangeAsync: async ({ value }) => {
              if (!value || value.length < 2 || value.length > 50) {
                return undefined; // Let onChange validation handle these cases
              }

              // Add a small delay to debounce the API calls
              await new Promise(resolve => setTimeout(resolve, 500));

              try {
                const isAvailable =
                  await authService.checkDisplayNameAvailability(value);
                if (!isAvailable) {
                  return 'Display name is already taken';
                }
                return undefined;
              } catch (error) {
                // Don't show error for network issues, let the user proceed
                return undefined;
              }
            },
          }}
        >
          {field => (
            <FormGroup
              label='Display Name'
              isRequired
              fieldId='simple-form-display-name-02'
            >
              <TextInput
                isRequired
                type='text'
                id='simple-form-display-name-02'
                name={field.name}
                value={field.state.value}
                onChange={(_event, value) => field.handleChange(value)}
                placeholder='Enter your display name (shown on reviews)'
                validated={
                  !field.state.meta.isTouched
                    ? 'default'
                    : field.state.meta.isValidating
                      ? 'default' // Show neutral state while validating
                      : field.state.meta.errors.length > 0
                        ? 'error'
                        : 'success'
                }
              />
              {field.state.meta.isValidating && (
                <div
                  style={{
                    color: '#6a6e73',
                    fontSize: '14px',
                    marginTop: '4px',
                  }}
                >
                  Checking availability...
                </div>
              )}
              {!field.state.meta.isValidating &&
                field.state.meta.errors.length > 0 && (
                  <div
                    style={{
                      color: '#c9190b',
                      fontSize: '14px',
                      marginTop: '4px',
                    }}
                  >
                    {field.state.meta.errors[0]}
                  </div>
                )}
            </FormGroup>
          )}
        </form.Field>
        <form.Field
          name='password'
          validators={{
            onChange: ({ value }) => {
              if (!value) {
                return 'Password is required';
              }
              if (!/^.{8,}$/.test(value)) {
                return 'Password must be at least 8 characters or longer';
              }
              if (!/^(?=.*?[#?!@$%^&*-]).{8,}$/.test(value)) {
                return 'Password must contain at least 1 special character';
              }
              if (!/^(?=.*?[A-Z]).{8,}$/.test(value)) {
                return 'Password must have at least 1 uppercase letter';
              }
              if (!/^(?=.*?[a-z]).{8,}$/.test(value)) {
                return 'Password must have at least 1 lowercase letter';
              }
              if (!/^(?=.*?[0-9]).{8,}$/.test(value)) {
                return 'Password must have at least 1 numerical character';
              }
              return undefined;
            },
          }}
        >
          {field => (
            <FormGroup
              label='Password'
              isRequired
              fieldId='simple-form-password-02'
            >
              <InputGroup>
                <InputGroupItem isFill>
                  <TextInput
                    isRequired
                    type={passwordHidden ? 'password' : 'text'}
                    id='simple-form-password-02'
                    name={field.name}
                    value={field.state.value}
                    onChange={(_event, value) => field.handleChange(value)}
                    validated={
                      !field.state.meta.isTouched
                        ? 'default'
                        : field.state.meta.errors.length > 0
                          ? 'error'
                          : 'success'
                    }
                  />
                </InputGroupItem>
                <InputGroupItem>
                  <Button
                    variant='control'
                    onClick={() => setPasswordHidden(!passwordHidden)}
                    aria-label={
                      passwordHidden
                        ? showPasswordAriaLabel
                        : hidePasswordAriaLabel
                    }
                    icon={passwordHidden ? <EyeIcon /> : <EyeSlashIcon />}
                  />
                </InputGroupItem>
              </InputGroup>
              {field.state.meta.errors.length > 0 && (
                <div
                  style={{
                    color: '#c9190b',
                    fontSize: '14px',
                    marginTop: '4px',
                  }}
                >
                  {field.state.meta.errors[0]}
                </div>
              )}
            </FormGroup>
          )}
        </form.Field>
        <form.Field
          name='age'
          validators={{
            onChange: ({ value }) => (!value ? 'Age is required' : undefined),
          }}
        >
          {field => (
            <FormGroup label='Age' isRequired fieldId='simple-form-number'>
              <TextInput
                isRequired
                type='number'
                id='simple-form-number'
                name={field.name}
                value={field.state.value}
                onChange={(_event, value) => field.handleChange(value)}
              />
            </FormGroup>
          )}
        </form.Field>
        <form.Field
          name='gender'
          validators={{
            onChange: ({ value }) =>
              !value ? 'Gender is required' : undefined,
          }}
        >
          {field => (
            <FormGroup
              role='radiogroup'
              isInline
              fieldId='limit-width-form-radio-group'
              label='Gender'
            >
              <Radio
                label='Male'
                name={field.name}
                id='radio-male'
                value='Male'
                isChecked={field.state.value === 'Male'}
                onChange={() => field.handleChange('Male')}
              />
              <Radio
                label='Female'
                name={field.name}
                id='radio-female'
                value='Female'
                isChecked={field.state.value === 'Female'}
                onChange={() => field.handleChange('Female')}
              />
              <Radio
                label='Other'
                name={field.name}
                id='radio-other'
                value='Other'
                isChecked={field.state.value === 'Other'}
                onChange={() => field.handleChange('Other')}
              />
            </FormGroup>
          )}
        </form.Field>
        <ActionGroup>
          <form.Subscribe
            selector={state => [
              state.canSubmit,
              state.isSubmitting,
              state.isPristine,
            ]}
          >
            {([canSubmit, isSubmitting]) => (
              <Button
                icon={<PaperPlaneIcon />}
                variant='primary'
                type='submit'
                isLoading={isSubmitting || signupMutation.isPending}
                isDisabled={
                  isSubmitting || signupMutation.isPending || !canSubmit
                }
              >
                {isSubmitting || signupMutation.isPending
                  ? 'Creating Account...'
                  : 'Create Account'}
              </Button>
            )}
          </form.Subscribe>
          <Button variant='link' onClick={handleCancel}>
            Cancel
          </Button>
        </ActionGroup>
      </Form>
    </>
  );

  const logIntoAccountMessage = (
    <LoginMainFooterBandItem>
      Already have an account? <Link to='/login'>Login.</Link>
    </LoginMainFooterBandItem>
  );

  return (
    <LoginPage
      loginTitle='Sign up for an account'
      signUpForAccountMessage={logIntoAccountMessage}
    >
      {signupForm}
    </LoginPage>
  );
};
