#include "Commandlets/AssetSnapshotCommandlet.h"
#include "AssetRegistry/AssetRegistryModule.h"
#include "AssetRegistry/IAssetRegistry.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

UAssetSnapshotCommandlet::UAssetSnapshotCommandlet()
{
    IsClient = false;
    IsServer = false;
    IsEditor = true;
    LogToConsole = true;
}

FString UAssetSnapshotCommandlet::ParseOutPath(const FString& Params) const
{
    FString OutPath;
    // Accept -out=<path> from command line
    if (!FParse::Value(*Params, TEXT("out="), OutPath))
    {
        OutPath = FPaths::ProjectSavedDir() / TEXT("AutomationReports/assets.snapshot.json");
    }
    return OutPath;
}

int32 UAssetSnapshotCommandlet::Main(const FString& Params)
{
    FString OutPath = ParseOutPath(Params);

    IAssetRegistry& AssetRegistry =
        FModuleManager::LoadModuleChecked<FAssetRegistryModule>(TEXT("AssetRegistry")).Get();

    // Wait for asset discovery to complete
    AssetRegistry.SearchAllAssets(true);

    TArray<FAssetData> AllAssets;
    AssetRegistry.GetAllAssets(AllAssets);

    TArray<TSharedPtr<FJsonValue>> AssetArray;
    AssetArray.Reserve(AllAssets.Num());

    for (const FAssetData& Asset : AllAssets)
    {
        TSharedRef<FJsonObject> Entry = MakeShared<FJsonObject>();
        Entry->SetStringField(TEXT("name"), Asset.AssetName.ToString());
        Entry->SetStringField(TEXT("package_path"), Asset.PackagePath.ToString());
        Entry->SetStringField(TEXT("asset_class"), Asset.AssetClassPath.GetAssetName().ToString());
        Entry->SetBoolField(TEXT("is_redirector"), Asset.IsRedirector());
        AssetArray.Add(MakeShared<FJsonValueObject>(Entry));
    }

    FString JsonString;
    TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&JsonString);
    FJsonSerializer::Serialize(AssetArray, Writer);

    IPlatformFile& PF = FPlatformFileManager::Get().GetPlatformFile();
    PF.CreateDirectoryTree(*FPaths::GetPath(OutPath));
    FFileHelper::SaveStringToFile(JsonString, *OutPath);

    UE_LOG(LogTemp, Display,
        TEXT("AssetSnapshot: wrote %d assets to %s"), AllAssets.Num(), *OutPath);
    return 0;
}
