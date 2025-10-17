import { useState } from 'react';
import {
  Button,
  InputGroup,
  TextInput,
  Tooltip,
  ToggleGroup,
  ToggleGroupItem,
  FileUpload,
} from '@patternfly/react-core';
import { LinkIcon, UploadIcon, ImageIcon } from '@patternfly/react-icons';
import { useNavigate } from '@tanstack/react-router';

export const ImageSearch: React.FC = () => {
  const [searchType, setSearchType] = useState<'url' | 'file'>('url');
  const [imageUrl, setImageUrl] = useState('');
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [filename, setFilename] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const navigate = useNavigate();

  // Helper function to store file temporarily in localStorage
  const storeTemporaryFile = (file: File): Promise<string> => {
    const fileId = `${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => {
        try {
          const fileData = {
            name: file.name,
            type: file.type,
            dataUrl: reader.result as string,
          };
          localStorage.setItem(
            `temp_image_${fileId}`,
            JSON.stringify(fileData)
          );
          resolve(fileId);
        } catch (error) {
          reject(error);
        }
      };
      reader.onerror = () => reject(reader.error);
      reader.readAsDataURL(file);
    });
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
      console.error('Navigation error:', error);
    } finally {
      setIsSearching(false);
    }
  };

  const handleFileSearch = async () => {
    if (!imageFile) return;
    setIsSearching(true);

    try {
      const fileId = await storeTemporaryFile(imageFile);
      navigate({
        to: '/image-search',
        search: { type: 'file', query: '', fileId },
      });
    } catch (error) {
      console.error('File storage or navigation error:', error);
    } finally {
      setIsSearching(false);
    }
  };

  const handleFileChange = (_event: any, file: File) => {
    setImageFile(file);
    setFilename(file.name);
  };

  const handleFileClear = () => {
    setImageFile(null);
    setFilename('');
  };

  return (
    <div>
      <div
        style={{
          display: 'flex',
          justifyContent: 'center',
          marginBottom: '24px',
        }}
      >
        <ToggleGroup
          aria-label='Search type selection'
          style={{
            background: 'white',
            borderRadius: '12px',
            padding: '4px',
            boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
            border: '1px solid #e9ecef',
          }}
        >
          <ToggleGroupItem
            icon={<LinkIcon />}
            text='Image URL'
            isSelected={searchType === 'url'}
            onChange={() => setSearchType('url')}
            style={{
              borderRadius: '8px',
              padding: '12px 20px',
              fontWeight: '500',
              transition: 'all 0.2s ease',
              ...(searchType === 'url' && {
                background: 'linear-gradient(135deg, #3498db 0%, #2980b9 100%)',
                color: 'white',
                boxShadow: '0 2px 4px rgba(52, 152, 219, 0.3)',
              }),
            }}
          />
          <ToggleGroupItem
            icon={<ImageIcon />}
            text='Upload Image'
            isSelected={searchType === 'file'}
            onChange={() => setSearchType('file')}
            style={{
              borderRadius: '8px',
              padding: '12px 20px',
              fontWeight: '500',
              transition: 'all 0.2s ease',
              ...(searchType === 'file' && {
                background: 'linear-gradient(135deg, #3498db 0%, #2980b9 100%)',
                color: 'white',
                boxShadow: '0 2px 4px rgba(52, 152, 219, 0.3)',
              }),
            }}
          />
        </ToggleGroup>
      </div>

      {searchType === 'url' ? (
        <div style={{ marginBottom: '24px' }}>
          <InputGroup style={{ gap: '8px' }}>
            <TextInput
              value={imageUrl}
              onChange={(_event, value) => setImageUrl(value)}
              onKeyDown={event => {
                if (event.key === 'Enter') {
                  handleUrlSearch();
                }
              }}
              placeholder='Enter image URL to find similar products...'
              type='url'
              aria-label='Image URL input'
              style={{
                borderRadius: '8px',
                padding: '12px 16px',
                fontSize: '16px',
                transition: 'border-color 0.2s ease',
                boxShadow: '0 2px 8px rgba(0,0,0,0.05)',
              }}
            />
            <Tooltip content='Search by image URL'>
              <Button
                variant='primary'
                onClick={handleUrlSearch}
                isDisabled={!imageUrl.trim() || isSearching}
                icon={<LinkIcon style={{ color: 'white' }} />}
                style={{
                  background:
                    'linear-gradient(135deg, #3498db 0%, #2980b9 100%)',
                  borderRadius: '8px',
                  padding: '12px 24px',
                  fontWeight: '600',
                  boxShadow: '0 2px 4px rgba(52, 152, 219, 0.3)',
                  transition: 'all 0.2s ease',
                  color: 'white',
                }}
              >
                Search
              </Button>
            </Tooltip>
          </InputGroup>
        </div>
      ) : (
        <div style={{ marginBottom: '24px' }}>
          <FileUpload
            id='image-file-upload'
            value={imageFile || undefined}
            filename={filename}
            filenamePlaceholder='Drag and drop an image file or upload one'
            onFileInputChange={handleFileChange}
            onClearClick={handleFileClear}
            browseButtonText='Upload Image'
            accept='image/*'
            allowEditingUploadedText={false}
            style={{
              border: '2px dashed #e9ecef',
              borderRadius: '12px',
              padding: '32px',
              textAlign: 'center',
              transition: 'border-color 0.2s ease',
              background: '#fafafa',
            }}
          />
          {imageFile && (
            <div style={{ textAlign: 'center', marginTop: '16px' }}>
              <Button
                variant='primary'
                onClick={handleFileSearch}
                isDisabled={isSearching}
                icon={<UploadIcon />}
                style={{
                  background:
                    'linear-gradient(135deg, #3498db 0%, #2980b9 100%)',
                  borderRadius: '8px',
                  padding: '12px 24px',
                  fontWeight: '600',
                  boxShadow: '0 2px 4px rgba(52, 152, 219, 0.3)',
                  transition: 'all 0.2s ease',
                }}
              >
                Search
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
