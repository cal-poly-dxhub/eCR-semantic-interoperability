from bedrock_client import BedrockClient
import json
import json_lines

def test_download_results():
    # Initialize the client
    print("\nInitializing BedrockClient...")
    client = BedrockClient(
        region='us-west-2',
        account_id='REMOVED_ID',
        profile_name='public-records-profile'
    )

    # Specify the bucket and folder prefix to test
    bucket_name = "batchinferencebuckettestbucketfeb15"
    s3_prefix = "output/nzt5i4umctak/"

    print(f"\nUsing bucket: {bucket_name}")
    print(f"Using prefix: {s3_prefix}")

    try:
        # Download results
        print("\nAttempting to download results...")
        results = client.download_batch_results(bucket_name, s3_prefix)
        
        # Print the results
        if results:
            print(f"\nSuccessfully downloaded {len(results)} results!")
            # Print the first result
            print("\nSample Result:")
            print(json.dumps(results[0], indent=2))
        else:
            print("\nNo results found in the specified location.")
            
    except Exception as e:
        print(f"\nAn error occurred during the test: {str(e)}")

if __name__ == "__main__":
    print("\nStarting test_download_results...")
    test_download_results()
    print("\nTest completed.")
