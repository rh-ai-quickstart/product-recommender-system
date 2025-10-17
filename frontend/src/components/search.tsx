import { useState } from 'react';
import {
  TextInput,
  Button,
  Tabs,
  Tab,
  TabTitleText,
  TabContent,
  TabContentBody,
  Card,
  CardBody,
} from '@patternfly/react-core';
import { SearchIcon } from '@patternfly/react-icons';
import { useNavigate } from '@tanstack/react-router';

export const Search: React.FunctionComponent = () => {
  const [value, setValue] = useState('');
  const [imageUrl, setImageUrl] = useState('');
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [isSearching, setIsSearching] = useState(false);
  const [activeTabKey, setActiveTabKey] = useState<string | number>(0);
  const navigate = useNavigate();

  // Helper function to store file temporarily in localStorage
  const storeTemporaryFile = (file: File): Promise<string> => {
    const fileId = `${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    console.log('Storing file:', {
      name: file.name,
      type: file.type,
      size: file.size,
    });

    return new Promise((resolve, reject) => {
      // Check file type first
      if (!file.type.startsWith('image/')) {
        console.error('Invalid file type:', file.type);
        reject(new Error('Please select a valid image file.'));
        return;
      }

      const reader = new FileReader();
      reader.onload = () => {
        try {
          const fileData = {
            name: file.name,
            type: file.type,
            dataUrl: reader.result as string,
          };

          const jsonString = JSON.stringify(fileData);
          console.log('File data size:', jsonString.length, 'characters');

          // Try to store the file and catch localStorage quota errors
          try {
            localStorage.setItem(`temp_image_${fileId}`, jsonString);
            console.log('File stored successfully with ID:', fileId);
            resolve(fileId);
          } catch (storageError) {
            console.error('localStorage error:', storageError);

            // Try to clear some space by removing old temp files
            const keys = Object.keys(localStorage);
            const tempKeys = keys.filter(key => key.startsWith('temp_image_'));
            console.log('Found', tempKeys.length, 'temporary files in storage');

            // Remove old temp files (older than 1 hour)
            const oneHourAgo = Date.now() - 60 * 60 * 1000;
            let removedCount = 0;

            tempKeys.forEach(key => {
              try {
                const timestamp = parseInt(key.split('_')[2] || '0');
                if (timestamp < oneHourAgo) {
                  localStorage.removeItem(key);
                  removedCount++;
                }
              } catch (e) {
                // Remove corrupted entries
                localStorage.removeItem(key);
                removedCount++;
              }
            });

            console.log('Cleaned up', removedCount, 'old temporary files');

            // Try storing again after cleanup
            try {
              localStorage.setItem(`temp_image_${fileId}`, jsonString);
              console.log(
                'File stored successfully after cleanup with ID:',
                fileId
              );
              resolve(fileId);
            } catch (secondError) {
              console.error('Still failed after cleanup:', secondError);
              reject(
                new Error(
                  'File is too large for browser storage. Please try a smaller image.'
                )
              );
            }
          }
        } catch (error) {
          console.error('Error processing file:', error);
          reject(new Error('Failed to process file.'));
        }
      };

      reader.onerror = () => {
        console.error('FileReader error:', reader.error);
        reject(new Error('Failed to read file.'));
      };

      reader.readAsDataURL(file);
    });
  };

  const onChange = (value: string) => {
    setValue(value);
  };

  const onSearch = (_event: React.FormEvent, value: string) => {
    if (value.trim()) {
      navigate({ to: '/search', search: { q: value.trim() } });
    }
  };

  const handleUrlSearch = async () => {
    if (!imageUrl.trim()) return;
    setIsSearching(true);
    try {
      navigate({
        to: '/image-search',
        search: { type: 'url', query: imageUrl.trim(), fileId: '' },
      });
    } catch (error) {
      console.error('URL search error:', error);
    } finally {
      setIsSearching(false);
    }
  };

  const handleFileSearch = async () => {
    if (!imageFile) {
      console.error('No image file selected');
      return;
    }

    console.log('Starting file search for:', imageFile.name);
    setIsSearching(true);

    try {
      const fileId = await storeTemporaryFile(imageFile);
      console.log('File stored, navigating with fileId:', fileId);

      navigate({
        to: '/image-search',
        search: { type: 'file', query: '', fileId },
      });
    } catch (error) {
      console.error('File search error:', error);

      // Show user-friendly error message
      if (error instanceof Error) {
        alert(`Upload failed: ${error.message}`);
      } else {
        alert('Upload failed. Please try again with a different image.');
      }
    } finally {
      setIsSearching(false);
    }
  };

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] || null;
    setImageFile(file);
  };

  const triggerFileUpload = () => {
    document.getElementById('file-upload-input')?.click();
  };

  const handleTabClick = (_: React.MouseEvent, tabIndex: string | number) => {
    setActiveTabKey(tabIndex);
  };

  return (
    <Card
      style={{
        borderRadius: '12px',
        border: '1px solid #dee2e6',
        boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
        width: '100%',
        padding: '0px',
      }}
    >
      <CardBody style={{ padding: '4px 10px' }}>
        <Tabs
          activeKey={activeTabKey}
          onSelect={handleTabClick}
          isBox={false}
          aria-label='Search options'
          style={{
            marginBottom: '8px',
          }}
        >
          <Tab
            eventKey={0}
            title={
              <TabTitleText style={{ fontWeight: '600' }}>Text</TabTitleText>
            }
            style={{
              borderRadius: '8px 8px 0 0',
            }}
          >
            <TabContent id='text-search-tab'>
              <TabContentBody style={{ padding: '8px 0' }}>
                <div
                  style={{ display: 'flex', gap: '8px', alignItems: 'center' }}
                >
                  <TextInput
                    placeholder='Search products...'
                    value={value}
                    onChange={(_event, value) => onChange(value)}
                    style={{
                      borderRadius: '8px',
                      // border: '1px solid #ced4da',
                      fontSize: '14px',
                      flex: 1,
                    }}
                  />
                  <Button
                    variant='primary'
                    onClick={() => onSearch({} as React.FormEvent, value)}
                    isDisabled={!value.trim() || isSearching}
                    icon={<SearchIcon />}
                    style={{
                      borderRadius: '4px',
                      padding: '6px 12px',
                      fontSize: '12px',
                      fontWeight: '600',
                      minWidth: '70px',
                    }}
                  >
                    {isSearching ? 'Searching...' : 'Search'}
                  </Button>
                </div>
              </TabContentBody>
            </TabContent>
          </Tab>
          <Tab
            eventKey={1}
            title={
              <TabTitleText style={{ fontWeight: '600' }}>URL</TabTitleText>
            }
            style={{
              borderRadius: '8px 8px 0 0',
            }}
          >
            <TabContent id='url-search-tab'>
              <TabContentBody style={{ padding: '8px 0' }}>
                <div
                  style={{ display: 'flex', gap: '8px', alignItems: 'center' }}
                >
                  <TextInput
                    placeholder='Paste image URL...'
                    value={imageUrl}
                    onChange={(_event, value) => setImageUrl(value)}
                    onKeyDown={event => {
                      if (event.key === 'Enter') {
                        handleUrlSearch();
                      }
                    }}
                    type='url'
                    style={{
                      borderRadius: '8px',
                      // border: '1px solid #ced4da',
                      fontSize: '14px',
                      flex: 1,
                    }}
                  />
                  <Button
                    variant='primary'
                    onClick={handleUrlSearch}
                    isDisabled={!imageUrl.trim() || isSearching}
                    icon={<SearchIcon />}
                    style={{
                      borderRadius: '4px',
                      padding: '6px 12px',
                      fontSize: '12px',
                      fontWeight: '600',
                      minWidth: '70px',
                    }}
                  >
                    {isSearching ? 'Searching...' : 'Search'}
                  </Button>
                </div>
              </TabContentBody>
            </TabContent>
          </Tab>
          <Tab
            eventKey={2}
            title={
              <TabTitleText style={{ fontWeight: '600' }}>Upload</TabTitleText>
            }
            style={{
              borderRadius: '8px 8px 0 0',
            }}
          >
            <TabContent id='upload-search-tab'>
              <TabContentBody style={{ padding: '8px 0' }}>
                <div
                  style={{ display: 'flex', gap: '8px', alignItems: 'center' }}
                >
                  <div
                    style={{
                      // border: '1px solid #ced4da',
                      borderRadius: '8px',
                      padding: '8px',
                      fontSize: '14px',
                      minHeight: '36px',
                      display: 'flex',
                      alignItems: 'center',
                      backgroundColor: '#f8f9fa',
                      flex: 1,
                    }}
                  >
                    <span
                      style={{
                        fontSize: '14px',
                        color: imageFile ? '#333' : '#6c757d',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {imageFile ? imageFile.name : 'No file selected'}
                    </span>
                  </div>
                  <Button
                    variant='secondary'
                    onClick={triggerFileUpload}
                    style={{
                      fontSize: '12px',
                      padding: '6px 12px',
                      borderRadius: '4px',
                      minWidth: '80px',
                    }}
                  >
                    Choose File
                  </Button>
                  <Button
                    variant='primary'
                    onClick={handleFileSearch}
                    isDisabled={!imageFile || isSearching}
                    icon={<SearchIcon />}
                    style={{
                      borderRadius: '4px',
                      padding: '6px 12px',
                      fontSize: '12px',
                      fontWeight: '600',
                      minWidth: '70px',
                    }}
                  >
                    {isSearching ? 'Searching...' : 'Search'}
                  </Button>
                  <input
                    id='file-upload-input'
                    type='file'
                    style={{ display: 'none' }}
                    accept='image/*'
                    onChange={handleFileChange}
                  />
                </div>
              </TabContentBody>
            </TabContent>
          </Tab>
        </Tabs>
      </CardBody>
    </Card>
  );
};
