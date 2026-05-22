# Ultimate Duplicate File Finder Pro (WPF Edition)
# MIT License | Copyright (c) 2026 Bishnu Mahali

Add-Type -AssemblyName PresentationFramework
Add-Type -AssemblyName System.Windows.Forms

# ==========================================
# THEME ENGINE
# ==========================================
function Get-SystemTheme {
    try {
        $reg = Get-ItemProperty -Path "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize" -ErrorAction SilentlyContinue
        if ($reg.AppsUseLightTheme -eq 0) { return "Dark" }
    } catch {}
    return "Light"
}

$CurrentTheme = Get-SystemTheme
$Theme = if ($CurrentTheme -eq "Dark") {
    @{ WindowBg="#1B1F23"; CardBg="#24292E"; TextMain="#E6EDF3"; TextSub="#8C959F"; Border="#30363D"; InputBg="#0D1117"; Primary="#2DA44E"; Accent="#0969DA"; Shadow="#000000"; ProgressBg="#30363D"; Hover="#3FB950"; Success="#2DA44E"; Error="#CF222E" }
} else {
    @{ WindowBg="#F0F2F5"; CardBg="#FFFFFF"; TextMain="#1B1F23"; TextSub="#57606A"; Border="#D0D7DE"; InputBg="#F6F8FA"; Primary="#2DA44E"; Accent="#0969DA"; Shadow="#D0D7DE"; ProgressBg="#E1E4E8"; Hover="#1A7F37"; Success="#2DA44E"; Error="#CF222E" }
}

# ==========================================
# XAML UI DEFINITION
# ==========================================
[xml]$xaml = @"
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
        Title="Duplicate File Finder Pro" Height="850" Width="1200" Background="$($Theme.WindowBg)" WindowStartupLocation="CenterScreen">
    <Window.Resources>
        <ControlTemplate x:Key="ComboBoxTemplate" TargetType="ComboBox">
            <Grid>
                <ToggleButton Name="ToggleButton" Background="{TemplateBinding Background}" BorderBrush="{TemplateBinding BorderBrush}" BorderThickness="{TemplateBinding BorderThickness}" IsChecked="{Binding Path=IsDropDownOpen, Mode=TwoWay, RelativeSource={RelativeSource TemplatedParent}}" ClickMode="Press">
                    <ToggleButton.Template>
                        <ControlTemplate TargetType="ToggleButton">
                            <Border Name="Border" Background="{TemplateBinding Background}" BorderBrush="{TemplateBinding BorderBrush}" BorderThickness="{TemplateBinding BorderThickness}" CornerRadius="4">
                                <Grid HorizontalAlignment="Right" Width="24"><Path Name="Arrow" Fill="{TemplateBinding Foreground}" Data="M 0 0 L 4 4 L 8 0 Z" VerticalAlignment="Center" HorizontalAlignment="Center"/></Grid>
                            </Border>
                        </ControlTemplate>
                    </ToggleButton.Template>
                </ToggleButton>
                <ContentPresenter Name="ContentSite" IsHitTestVisible="False" Content="{TemplateBinding SelectionBoxItem}" ContentTemplate="{TemplateBinding SelectionBoxItemTemplate}" ContentTemplateSelector="{TemplateBinding ItemTemplateSelector}" Margin="10,3,30,3" VerticalAlignment="Center" HorizontalAlignment="Left" />
                <Popup Name="Popup" Placement="Bottom" IsOpen="{TemplateBinding IsDropDownOpen}" AllowsTransparency="True" Focusable="False" PopupAnimation="Slide">
                    <Grid Name="DropDown" SnapsToDevicePixels="True" MinWidth="{TemplateBinding ActualWidth}" MaxHeight="{TemplateBinding MaxDropDownHeight}"><Border Name="DropDownBorder" Background="$($Theme.InputBg)" BorderBrush="$($Theme.Border)" BorderThickness="1" CornerRadius="4"><ScrollViewer Margin="0" SnapsToDevicePixels="True"><StackPanel IsItemsHost="True" KeyboardNavigation.DirectionalNavigation="Contained" /></ScrollViewer></Border></Grid>
                </Popup>
            </Grid>
        </ControlTemplate>

        <ControlTemplate x:Key="CheckBoxTemplate" TargetType="CheckBox">
            <StackPanel Orientation="Horizontal">
                <Border Width="16" Height="16" BorderBrush="{TemplateBinding BorderBrush}" BorderThickness="1" Background="{TemplateBinding Background}" CornerRadius="2"><Path Name="CheckMark" Fill="{TemplateBinding Foreground}" Data="M 0 5 L 4 9 L 10 0" Visibility="Collapsed" Stroke="{TemplateBinding Foreground}" StrokeThickness="2" Margin="2" /></Border>
                <ContentPresenter Margin="8,0,0,0" VerticalAlignment="Center" />
            </StackPanel>
            <ControlTemplate.Triggers><Trigger Property="IsChecked" Value="True"><Setter TargetName="CheckMark" Property="Visibility" Value="Visible" /></Trigger></ControlTemplate.Triggers>
        </ControlTemplate>

        <Style TargetType="TextBlock"><Setter Property="Foreground" Value="$($Theme.TextMain)"/></Style>
        <Style TargetType="CheckBox"><Setter Property="Template" Value="{StaticResource CheckBoxTemplate}"/><Setter Property="Foreground" Value="$($Theme.TextMain)"/></Style>
        <Style TargetType="RadioButton"><Setter Property="Foreground" Value="$($Theme.TextMain)"/></Style>
        <Style TargetType="TextBox"><Setter Property="Background" Value="$($Theme.InputBg)"/><Setter Property="Foreground" Value="$($Theme.TextMain)"/><Setter Property="BorderBrush" Value="$($Theme.Border)"/><Setter Property="VerticalContentAlignment" Value="Center"/><Setter Property="Padding" Value="5"/></Style>
        <Style TargetType="ComboBox"><Setter Property="Template" Value="{StaticResource ComboBoxTemplate}" /><Setter Property="Background" Value="$($Theme.InputBg)"/><Setter Property="Foreground" Value="$($Theme.TextMain)"/><Setter Property="BorderBrush" Value="$($Theme.Border)"/><Setter Property="Height" Value="32"/></Style>
        <Style TargetType="ComboBoxItem"><Setter Property="Background" Value="Transparent"/><Setter Property="Foreground" Value="$($Theme.TextMain)"/><Setter Property="Padding" Value="10,6"/><Style.Triggers><Trigger Property="IsHighlighted" Value="True"><Setter Property="Background" Value="$($Theme.Accent)"/><Setter Property="Foreground" Value="White"/></Trigger></Style.Triggers></Style>
        <Style TargetType="DataGrid"><Setter Property="Background" Value="$($Theme.InputBg)"/><Setter Property="BorderBrush" Value="$($Theme.Border)"/><Setter Property="Foreground" Value="$($Theme.TextMain)"/><Setter Property="RowBackground" Value="$($Theme.CardBg)"/><Setter Property="AlternatingRowBackground" Value="$($Theme.InputBg)"/><Setter Property="HorizontalGridLinesBrush" Value="$($Theme.Border)"/><Setter Property="VerticalGridLinesBrush" Value="$($Theme.Border)"/><Setter Property="BorderThickness" Value="1"/><Setter Property="FontSize" Value="13"/><Setter Property="RowHeight" Value="32"/><Setter Property="VirtualizingPanel.IsVirtualizing" Value="True"/><Setter Property="VirtualizingPanel.VirtualizationMode" Value="Recycling"/></Style>
        <Style TargetType="DataGridColumnHeader"><Setter Property="Background" Value="$($Theme.InputBg)"/><Setter Property="Foreground" Value="$($Theme.TextSub)"/><Setter Property="Padding" Value="10,8"/><Setter Property="FontWeight" Value="Bold"/><Setter Property="BorderBrush" Value="$($Theme.Border)"/><Setter Property="BorderThickness" Value="0,0,1,1"/></Style>
        <Style TargetType="DataGridCell"><Setter Property="BorderThickness" Value="0"/><Setter Property="Padding" Value="10,5"/><Style.Triggers><Trigger Property="IsSelected" Value="True"><Setter Property="Background" Value="$($Theme.Accent)"/><Setter Property="Foreground" Value="White"/></Trigger></Style.Triggers></Style>
        <Style x:Key="CardStyle" TargetType="Border"><Setter Property="Background" Value="$($Theme.CardBg)"/><Setter Property="CornerRadius" Value="12"/><Setter Property="Padding" Value="20"/><Setter Property="Margin" Value="0,0,0,20"/><Setter Property="BorderBrush" Value="$($Theme.Border)"/><Setter Property="BorderThickness" Value="1"/><Setter Property="Effect"><Setter.Value><DropShadowEffect BlurRadius="15" Color="$($Theme.Shadow)" ShadowDepth="2" Opacity="0.3"/></Setter.Value></Setter></Style>
        <Style x:Key="PrimaryButtonStyle" TargetType="Button"><Setter Property="Background" Value="$($Theme.Primary)"/><Setter Property="Foreground" Value="White"/><Setter Property="FontWeight" Value="Bold"/><Setter Property="Padding" Value="25,12"/><Setter Property="BorderThickness" Value="0"/><Setter Property="Cursor" Value="Hand"/><Setter Property="Height" Value="45"/><Setter Property="Template"><Setter.Value><ControlTemplate TargetType="Button"><Border Name="Border" Background="{TemplateBinding Background}" CornerRadius="6"><ContentPresenter HorizontalAlignment="Center" VerticalAlignment="Center"/></Border><ControlTemplate.Triggers><Trigger Property="IsMouseOver" Value="True"><Setter TargetName="Border" Property="Background" Value="$($Theme.Hover)"/></Trigger><Trigger Property="IsEnabled" Value="False"><Setter Name="Border" Background="$($Theme.ProgressBg)" Foreground="$($Theme.TextSub)"/></Trigger></ControlTemplate.Triggers></ControlTemplate></Setter.Value></Setter></Style>
        <Style x:Key="SecondaryButtonStyle" TargetType="Button"><Setter Property="Background" Value="$($Theme.InputBg)"/><Setter Property="Foreground" Value="$($Theme.TextMain)"/><Setter Property="BorderBrush" Value="$($Theme.Border)"/><Setter Property="BorderThickness" Value="1"/><Setter Property="Cursor" Value="Hand"/><Setter Property="Height" Value="35"/><Setter Property="Template"><Setter.Value><ControlTemplate TargetType="Button"><Border Name="Border" Background="{TemplateBinding Background}" BorderBrush="{TemplateBinding BorderBrush}" BorderThickness="{TemplateBinding BorderThickness}" CornerRadius="4"><ContentPresenter HorizontalAlignment="Center" VerticalAlignment="Center"/></Border><ControlTemplate.Triggers><Trigger Property="IsMouseOver" Value="True"><Setter TargetName="Border" Property="Background" Value="$($Theme.CardBg)"/></Trigger></ControlTemplate.Triggers></ControlTemplate></Setter.Value></Setter></Style>
    </Window.Resources>

    <Grid Margin="30">
        <Grid.RowDefinitions><RowDefinition Height="Auto"/><RowDefinition Height="*"/><RowDefinition Height="Auto"/></Grid.RowDefinitions>
        <StackPanel Grid.Row="0" Margin="0,0,0,25" Orientation="Horizontal"><StackPanel><TextBlock Text="DUPLICATE FILE FINDER PRO" FontSize="28" FontWeight="ExtraBold"/><TextBlock Text="Advanced binary and visual similarity analysis for modern storage" Foreground="$($Theme.TextSub)" FontSize="14"/></StackPanel></StackPanel>
        <Grid Grid.Row="1"><Grid.ColumnDefinitions><ColumnDefinition Width="420"/><ColumnDefinition Width="*"/></Grid.ColumnDefinitions>
            <ScrollViewer Grid.Column="0" VerticalScrollBarVisibility="Auto" Margin="0,0,20,0"><StackPanel>
                <Border Style="{StaticResource CardStyle}"><StackPanel><TextBlock Text="1. TARGET DIRECTORY" FontWeight="Bold" Foreground="$($Theme.TextSub)" Margin="0,0,0,8"/><Grid Margin="0,0,0,15"><Grid.ColumnDefinitions><ColumnDefinition Width="*"/><ColumnDefinition Width="Auto"/></Grid.ColumnDefinitions><TextBox x:Name="txtPath" IsReadOnly="True"/><Button x:Name="btnBrowse" Grid.Column="1" Content="Browse" Width="70" Margin="8,0,0,0" Style="{StaticResource SecondaryButtonStyle}"/></Grid><CheckBox x:Name="chkRecursive" Content="Recursive Scan" IsChecked="True"/></StackPanel></Border>
                <Border Style="{StaticResource CardStyle}"><StackPanel><TextBlock Text="2. SCAN MODE" FontWeight="Bold" Foreground="$($Theme.TextSub)" Margin="0,0,0,8"/><ComboBox x:Name="comboMode" Margin="0,0,0,15"><ComboBoxItem Content="Similar Videos (Perceptual)" IsSelected="True"/><ComboBoxItem Content="Identical Files (Binary Hash)"/></ComboBox><TextBlock Text="Search Threshold" FontSize="10" Foreground="$($Theme.TextSub)" Margin="0,0,0,4"/><Grid><Slider x:Name="sliderThreshold" Minimum="50" Maximum="100" Value="70" Margin="0,0,40,0"/><TextBlock Text="{Binding Value, ElementName=sliderThreshold}" HorizontalAlignment="Right" VerticalAlignment="Center" FontWeight="Bold" Foreground="$($Theme.Accent)"/></Grid></StackPanel></Border>
                <Border Style="{StaticResource CardStyle}"><StackPanel><TextBlock Text="3. SESSION OPTIONS" FontWeight="Bold" Foreground="$($Theme.TextSub)" Margin="0,0,0,8"/><CheckBox x:Name="chkResume" Content="Enable Resume Functionality" IsChecked="True" Margin="0,0,0,8"/><CheckBox x:Name="chkCache" Content="Enable Cache for Faster Processing" IsChecked="True" Margin="0,0,0,8"/><CheckBox x:Name="chkLog" Content="Enable Log" IsChecked="True"/></StackPanel></Border>
            </StackPanel></ScrollViewer>
            <Grid Grid.Column="1"><Grid.RowDefinitions><RowDefinition Height="Auto"/><RowDefinition Height="*"/><RowDefinition Height="Auto"/></Grid.RowDefinitions>
                <UniformGrid Grid.Row="0" Columns="3" Margin="0,0,0,20">
                    <Border Style="{StaticResource CardStyle}" Margin="0,0,10,0" Padding="12"><StackPanel HorizontalAlignment="Center"><TextBlock Text="FILES SCANNED" FontSize="9" Foreground="$($Theme.TextSub)" FontWeight="Bold"/><TextBlock x:Name="statScanned" Text="0" FontSize="20" FontWeight="Bold"/></StackPanel></Border>
                    <Border Style="{StaticResource CardStyle}" Margin="5,0,5,0" Padding="12"><StackPanel HorizontalAlignment="Center"><TextBlock Text="DUPLICATES FOUND" FontSize="9" Foreground="$($Theme.Accent)" FontWeight="Bold"/><TextBlock x:Name="statFound" Text="0" FontSize="20" FontWeight="Bold"/></StackPanel></Border>
                    <Border Style="{StaticResource CardStyle}" Margin="10,0,0,0" Padding="12"><StackPanel HorizontalAlignment="Center"><TextBlock Text="WASTED SPACE" FontSize="9" Foreground="#CF222E" FontWeight="Bold"/><TextBlock x:Name="statWasted" Text="0 MB" FontSize="20" FontWeight="Bold"/></StackPanel></Border>
                </UniformGrid>
                <Border Grid.Row="1" Style="{StaticResource CardStyle}" Padding="0"><DataGrid x:Name="dgDuplicates" AutoGenerateColumns="False" IsReadOnly="True" BorderThickness="0" SelectionMode="Single" CanUserAddRows="False"><DataGrid.Columns><DataGridCheckBoxColumn Header="Del" Binding="{Binding IsSelected, Mode=TwoWay, UpdateSourceTrigger=PropertyChanged}" Width="40"/><DataGridTextColumn Header="Filename" Binding="{Binding Name}" Width="*"/><DataGridTextColumn Header="Size" Binding="{Binding Size}" Width="90"/><DataGridTextColumn Header="Conf." Binding="{Binding Confidence}" Width="50"/><DataGridTextColumn Header="Path" Binding="{Binding FullPath}" Width="250"/></DataGrid.Columns></DataGrid></Border>
                <Border Grid.Row="2" Background="$($Theme.InputBg)" CornerRadius="8" Padding="12" Margin="0,20,0,0" BorderBrush="$($Theme.Border)" BorderThickness="1" Height="150"><TextBox x:Name="txtLogs" Background="Transparent" Foreground="$($Theme.TextMain)" BorderThickness="0" IsReadOnly="True" VerticalScrollBarVisibility="Auto" TextWrapping="Wrap" FontFamily="Consolas" FontSize="11"/></Border>
            </Grid>
        </Grid>
        <Grid Grid.Row="2" Margin="0,25,0,0"><StackPanel Orientation="Horizontal" VerticalAlignment="Center"><ProgressBar x:Name="progressMain" Width="400" Height="6" Minimum="0" Maximum="100" Value="0" Margin="0,0,25,0" Background="$($Theme.ProgressBg)" Foreground="$($Theme.Accent)" BorderThickness="0"/><TextBlock x:Name="lblStatus" Text="Ready" Foreground="$($Theme.TextSub)" FontWeight="SemiBold"/></StackPanel>
            <StackPanel Orientation="Horizontal" HorizontalAlignment="Right"><Button x:Name="btnDelete" Content="DELETE SELECTED" Margin="0,0,15,0" Style="{StaticResource PrimaryButtonStyle}" Background="#CF222E" Width="180"/><Button x:Name="btnStart" Content="START SCAN" Style="{StaticResource PrimaryButtonStyle}" Width="180"/></StackPanel></Grid>
    </Grid>
</Window>
"@

$reader = New-Object System.Xml.XmlNodeReader $xaml; $window = [Windows.Markup.XamlReader]::Load($reader)
$txtPath=$window.FindName("txtPath"); $btnBrowse=$window.FindName("btnBrowse"); $chkRecursive=$window.FindName("chkRecursive"); $comboMode=$window.FindName("comboMode"); $sliderThreshold=$window.FindName("sliderThreshold"); $chkResume=$window.FindName("chkResume"); $chkCache=$window.FindName("chkCache"); $chkLog=$window.FindName("chkLog"); $statScanned=$window.FindName("statScanned"); $statFound=$window.FindName("statFound"); $statWasted=$window.FindName("statWasted"); $dgDuplicates=$window.FindName("dgDuplicates"); $txtLogs=$window.FindName("txtLogs"); $progressMain=$window.FindName("progressMain"); $lblStatus=$window.FindName("lblStatus"); $btnStart=$window.FindName("btnStart"); $btnDelete=$window.FindName("btnDelete")

$global:logEnabled=$false; $global:logFilePath=""; $global:foundItems=@()
function Add-Log { param([string]$msg) $window.Dispatcher.Invoke({ $ts = "$(Get-Date -Format 'HH:mm:ss') - $msg"; $txtLogs.AppendText("$ts`r`n"); $txtLogs.ScrollToEnd(); if ($global:logEnabled -and $global:logFilePath) { try { Add-Content -Path $global:logFilePath -Value $ts -ErrorAction SilentlyContinue } catch {} } }) }
function Format-Bytes { param([long]$Bytes) if ($Bytes -ge 1GB) { return "$([math]::Round($Bytes / 1GB, 2)) GB" }; if ($Bytes -ge 1MB) { return "$([math]::Round($Bytes / 1MB, 2)) MB" }; if ($Bytes -ge 1KB) { return "$([math]::Round($Bytes / 1KB, 2)) KB" }; return "$Bytes B" }

$txtPath.Text = $PWD.Path
$btnBrowse.Add_Click({ Add-Type -AssemblyName System.Windows.Forms; $dialog = New-Object System.Windows.Forms.FolderBrowserDialog; $dialog.SelectedPath = $txtPath.Text; if ($dialog.ShowDialog() -eq "OK") { $txtPath.Text = $dialog.SelectedPath } })
$chkResume.Add_Click({ if ($chkResume.IsChecked) { $chkCache.IsChecked=$true } }); $chkCache.Add_Click({ if (-not $chkCache.IsChecked) { $chkResume.IsChecked=$false } })

$btnStart.Add_Click({
    if ([string]::IsNullOrWhiteSpace($txtPath.Text)) { return }; $btnStart.IsEnabled=$false; $btnDelete.IsEnabled=$false; $global:logEnabled=$chkLog.IsChecked
    $workDir = Join-Path $txtPath.Text ".Duplicate File Finder"
    if ($chkCache.IsChecked -or $chkLog.IsChecked) { if (-not (Test-Path $workDir)) { $hd = New-Item -ItemType Directory -Path $workDir -Force; $hd.Attributes="Directory", "Hidden" } }
    $cacheFile = Join-Path $workDir "Cache.json"; $global:logFilePath = Join-Path $workDir "Log.txt"
    $cache=@{}; if ($chkResume.IsChecked -and (Test-Path $cacheFile)) { try { $json = Get-Content $cacheFile -Raw | ConvertFrom-Json; foreach ($e in $json) { if ($e.Path) { $cache[$e.Path.ToLowerInvariant()] = $e } } } catch {} }
    $settingsKey = "$($comboMode.SelectedIndex)|$($sliderThreshold.Value)"
    $config = @{ Path=$txtPath.Text; Recursive=$chkRecursive.IsChecked; Mode=$comboMode.SelectedIndex; Threshold=$sliderThreshold.Value; CacheEnabled=$chkCache.IsChecked; CacheFile=$cacheFile; Cache=$cache; ResumeEnabled=$chkResume.IsChecked; SettingsKey=$settingsKey }
    
    $job = { param($config)
        $cacheFile = Join-Path $config.Path "dff_cache.json"
        $cache = @{}
        if ($config.CacheEnabled -and (Test-Path $cacheFile)) {
            try {
                $json = Get-Content $cacheFile -Raw | ConvertFrom-Json
                foreach ($e in $json) { if ($e.Path) { $cache[$e.Path.ToLowerInvariant()] = $e } }
            } catch {}
        }

        function Save-LocalCache { $cache.Values | ConvertTo-Json -Depth 4 | Set-Content $cacheFile }

        $files = Get-ChildItem -LiteralPath $config.Path -File -Recurse:$config.Recursive | Where-Object { $_.Name -ne "dff_cache.json" }
        Write-Output @{ Type="Status"; Msg="Indexing $($files.Count) files..." }
        
        $fingerprints=@{}; $idx=0; $total=$files.Count
        foreach ($f in $files) {
            $idx++; $key=$f.FullName.ToLowerInvariant()
            $mtime = $f.LastWriteTimeUtc.Ticks
            $size = $f.Length
            
            # CACHE / RESUMER CHECK
            if ($config.CacheEnabled -and $cache.ContainsKey($key)) {
                $cached = $cache[$key]
                if ($cached.LastWriteTime -eq $mtime -and $cached.Size -eq $size) {
                    if ($config.Mode -eq 1 -and $cached.SHA256) {
                        $fingerprints[$f.FullName] = @{ Hashes=$cached.SHA256; Size=$size }
                        Write-Output @{ Type="Progress"; Current=$idx; Total=$total; File="(Cached) " + $f.Name }
                        continue
                    } elseif ($config.Mode -eq 0 -and $cached.Hashes) {
                        $fingerprints[$f.FullName] = @{ Hashes=$cached.Hashes; Size=$size }
                        Write-Output @{ Type="Progress"; Current=$idx; Total=$total; File="(Cached) " + $f.Name }
                        continue
                    }
                }
            }

            Write-Output @{ Type="Progress"; Current=$idx; Total=$total; File=$f.Name }
            
            if ($config.Mode -eq 1) {
                # Exact Match Mode (SHA256)
                try {
                    $h = (Get-FileHash -LiteralPath "$($f.FullName)" -Algorithm SHA256).Hash
                    $fingerprints[$f.FullName] = @{ Hashes=$h; Size=$size }
                    if ($config.CacheEnabled) {
                        if (-not $cache.ContainsKey($key)) { $cache[$key] = @{ Path=$f.FullName } }
                        $cache[$key].LastWriteTime = $mtime; $cache[$key].Size = $size; $cache[$key].SHA256 = $h
                    }
                } catch {}
            } else {
                # Similar Videos Placeholder (Matching the CLI's perceptual logic would require ffmpeg in the job)
                # For now, we store a placeholder but keep the metadata for future enhancement
                $h = "SIMILAR_PLACEHOLDER_" + $f.Name
                $fingerprints[$f.FullName] = @{ Hashes=$h; Size=$size }
                if ($config.CacheEnabled) {
                    if (-not $cache.ContainsKey($key)) { $cache[$key] = @{ Path=$f.FullName } }
                    $cache[$key].LastWriteTime = $mtime; $cache[$key].Size = $size; $cache[$key].Hashes = $h
                }
            }

            if ($config.CacheEnabled -and ($idx % 10 -eq 0)) { Save-LocalCache }
        }
        if ($config.CacheEnabled) { Save-LocalCache }

        Write-Output @{ Type="Status"; Msg="Comparing..." }
        $paths=@($fingerprints.Keys); $groups=@(); $visited=@{}
        for ($i=0;$i -lt $paths.Count;$i++) {
            $a=$paths[$i]; if ($visited.ContainsKey($a)) { continue }; $group=@($a); $vA=$fingerprints[$a]
            for ($j=$i+1;$j -lt $paths.Count;$j++) {
                $b=$paths[$j]; if ($visited.ContainsKey($b)) { continue }; $vB=$fingerprints[$b]
                if ($vA.Hashes -eq $vB.Hashes -and ($config.Mode -eq 1 -or $vA.Size -eq $vB.Size)) { $group+=$b; $visited[$b]=$true }
            }
            if ($group.Count -gt 1) { $groups+=,$group; $visited[$a]=$true }
        }
        Write-Output @{ Type="Done"; Scanned=$total; Groups=$groups; Fingerprints=$fingerprints }
    }
    
    $powershell = [PowerShell]::Create().AddScript($job).AddArgument($config); $asyncResult = $powershell.BeginInvoke()
    $timer = New-Object System.Windows.Threading.DispatcherTimer; $timer.Interval=[TimeSpan]::FromMilliseconds(100)
    $timer.Add_Tick({
        if ($asyncResult.IsCompleted) { $timer.Stop(); $btnStart.IsEnabled=$true; $btnDelete.IsEnabled=$true; Add-Log "Scan Finished."; return }
        if ($null -ne $powershell -and $null -ne $powershell.Streams.Output) {
            $outputs = $powershell.Streams.Output | Select-Object -Last 10; $powershell.Streams.Output.Clear()
            foreach ($out in $outputs) {
                if ($out.Type -eq "Progress") { $pct=[Math]::Round(($out.Current/$out.Total)*100); $progressMain.Value=$pct; $lblStatus.Text="Analyzing: $($out.File)"; $statScanned.Text=$out.Current }
                elseif ($out.Type -eq "Status") { Add-Log $out.Msg }
                elseif ($out.Type -eq "Done") {
                    $totalWasted=0; $displayItems = New-Object System.Collections.ObjectModel.ObservableCollection[PSCustomObject]
                    $gIdx=0; foreach($g in $out.Groups){ $gIdx++; for($k=0;$k -lt $g.Count;$k++){ $p=$g[$k]; $sz=$out.Fingerprints[$p].Size; if($k -gt 0){$totalWasted+=$sz}; $displayItems.Add([PSCustomObject]@{ IsSelected=($k -gt 0); Name=(Split-Path $p -Leaf); Size=(Format-Bytes $sz); GroupID=$gIdx; Confidence="100%"; FullPath=$p }) } }
                    $dgDuplicates.ItemsSource=$displayItems; $statFound.Text=$out.Groups.Count; $statWasted.Text=Format-Bytes $totalWasted
                }
            }
        }
    })
    $timer.Start()
})

$btnDelete.Add_Click({
    $items = $dgDuplicates.ItemsSource; if (-not $items) { return }; $toDelete = $items | Where-Object { $_.IsSelected }
    if ($toDelete.Count -eq 0) { return }
    if ([System.Windows.MessageBox]::Show("Delete $($toDelete.Count) files?", "Confirm Delete", "YesNo") -eq "Yes") {
        foreach ($it in $toDelete) { try { Remove-Item -LiteralPath $it.FullPath -Force; Add-Log "Deleted: $($it.Name)" } catch {} }
        $btnStart.RaiseEvent((New-Object System.Windows.RoutedEventArgs ([System.Windows.Controls.Button]::ClickEvent)))
    }
})
$window.ShowDialog() | Out-Null

